/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.tv

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.IBinder
import android.util.Log
import app.tvsitter.rules.contract.Command
import app.tvsitter.rules.contract.StateSnapshot
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch

/**
 * The heart of the app: it watches what is on screen, counts the time, and puts the lock up.
 *
 * A foreground service rather than an accessibility service, per D16. The privilege that buys
 * is the whole point — "draw on top" instead of "read everything on screen and every
 * keystroke" — and it stops password fields being unmasked system-wide, which merely having
 * an accessibility service enabled does (D15).
 *
 * The cost is that nothing revives this for free. An accessibility service came back about 27
 * seconds after a reboot without being asked; this has to restart itself from
 * `BOOT_COMPLETED`, stay sticky, and expect to be killed.
 */
class EnforcerService : Service() {

    private var overlay: LockOverlay? = null
    private var screenState: ScreenState? = null
    private var appLabels: AppLabels? = null
    private var foregroundApps: ForegroundAppMonitor? = null
    private var mqtt: MqttBridge? = null

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)
    private var pendingPublish: Job? = null

    val foregroundPackage: String? get() = foregroundApps?.current

    val isLocked: Boolean get() = overlay?.isShowing == true

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        instance = this
        startForegroundNotification()

        overlay = LockOverlay(this)
        appLabels = AppLabels(this)
        foregroundApps = ForegroundAppMonitor(this) { publishSoon() }
        screenState = ScreenState(this) { publishSoon() }.also { it.start() }

        Log.i(
            TAG,
            "onCreate(): version=${BuildConfig.VERSION_NAME} api=${Build.VERSION.SDK_INT} " +
                "model=${Build.MODEL} manufacturer=${Build.MANUFACTURER}",
        )

        scope.launch { startMqtt() }
        scope.launch { watchForeground() }
        scope.launch { heartbeat() }
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_LOCK -> lock(intent.getStringExtra(EXTRA_REASON) ?: getString(R.string.lock_title))
            ACTION_UNLOCK -> unlock()
        }
        // Sticky because there is no longer anything else to bring this back: if the system
        // kills the process, restarting it is the only way the counter resumes.
        return START_STICKY
    }

    fun lock(reason: String) {
        overlay?.show(
            title = getString(R.string.lock_title),
            subtitle = reason,
            onAskForTime = { Log.i(TAG, "TODO M3: request for more time") },
        )
        publishSoon()
    }

    fun unlock() {
        overlay?.hide()
        publishSoon()
    }

    private suspend fun startMqtt() {
        val config = Settings(this).broker.first()
        if (!config.isComplete) {
            Log.w(TAG, "mqtt: not configured, nothing will be published (see tools/device.sh configure)")
            return
        }
        mqtt = MqttBridge(config, ::handleCommand).also { it.connect() }
    }

    /** Drops any existing connection and reconnects with whatever is now stored. */
    fun reconnectMqtt() {
        scope.launch {
            mqtt?.disconnect()
            mqtt = null
            startMqtt()
        }
    }

    private fun handleCommand(command: Command) {
        when (command) {
            is Command.Lock -> lock(command.reason ?: getString(R.string.lock_title))
            is Command.Unlock -> unlock()
            is Command.Ping -> publishSoon()
            is Command.StopApp -> Log.i(TAG, "TODO M2: stop ${command.pkg}")
            is Command.Grant, is Command.Deny -> Log.i(TAG, "TODO M3: $command")
            is Command.SetRules -> Log.i(TAG, "TODO M4: rules rev ${command.rev}")
        }
    }

    /**
     * Polling replaces the accessibility service's window events. The interval is a
     * compromise: fast enough that it does not matter for counting, slow enough to be
     * unremarkable on a mains-powered device. It does mean a newly opened app is visible for
     * a moment before the lock lands, which D16 accepts knowingly.
     */
    private suspend fun watchForeground() {
        val monitor = foregroundApps ?: return
        if (!monitor.isUsable) {
            Log.e(TAG, "usage stats unavailable — nothing will be detected")
            return
        }
        while (scope.isActive) {
            if (screenState?.isScreenOn != false) monitor.poll()
            delay(FOREGROUND_POLL_MS)
        }
    }

    private fun publishSoon() {
        pendingPublish?.cancel()
        pendingPublish = scope.launch {
            delay(PUBLISH_DEBOUNCE_MS)
            publishNow()
        }
    }

    private suspend fun heartbeat() {
        while (scope.isActive) {
            delay(HEARTBEAT_MS)
            publishNow()
        }
    }

    private fun publishNow() {
        val bridge = mqtt ?: return
        val pkg = foregroundApps?.current
        bridge.publish(
            StateSnapshot(
                ts = System.currentTimeMillis(),
                fw = BuildConfig.VERSION_NAME,
                screenOn = screenState?.isScreenOn ?: false,
                locked = isLocked,
                appId = pkg,
                appName = pkg?.let { appLabels?.labelOf(it) },
                // Counters arrive with the rules engine in M2; publishing zeroes now would
                // be a lie, so the fields keep their "nothing known yet" defaults.
                remainingTodaySeconds = null,
            ),
        )
    }

    private fun startForegroundNotification() {
        val manager = getSystemService(NotificationManager::class.java)
        manager?.createNotificationChannel(
            NotificationChannel(
                CHANNEL_ID,
                getString(R.string.notification_channel),
                NotificationManager.IMPORTANCE_LOW,
            ),
        )
        val notification = Notification.Builder(this, CHANNEL_ID)
            .setContentTitle(getString(R.string.app_name))
            .setContentText(getString(R.string.notification_running))
            .setSmallIcon(R.drawable.banner)
            .setOngoing(true)
            .build()

        // The typed overload exists from API 29 and specialUse from 34; minSdk is 26.
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE) {
            startForeground(
                NOTIFICATION_ID,
                notification,
                ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE,
            )
        } else {
            startForeground(NOTIFICATION_ID, notification)
        }
    }

    override fun onDestroy() {
        Log.w(TAG, "onDestroy(): the enforcer is going down")
        mqtt?.disconnect()
        mqtt = null
        screenState?.stop()
        screenState = null
        overlay?.hide()
        overlay = null
        appLabels = null
        foregroundApps = null
        instance = null
        scope.cancel()
        super.onDestroy()
    }

    companion object {
        const val TAG = "TVSitter"

        const val ACTION_LOCK = "app.tvsitter.tv.action.LOCK"
        const val ACTION_UNLOCK = "app.tvsitter.tv.action.UNLOCK"
        const val EXTRA_REASON = "reason"

        private const val CHANNEL_ID = "tvsitter_enforcer"
        private const val NOTIFICATION_ID = 1
        private const val PUBLISH_DEBOUNCE_MS = 400L
        private const val HEARTBEAT_MS = 60_000L
        private const val FOREGROUND_POLL_MS = 1_500L

        @Volatile
        var instance: EnforcerService? = null
            private set

        /** Starts the service if it is not already running. Safe to call repeatedly. */
        fun start(context: android.content.Context) {
            context.startForegroundService(Intent(context, EnforcerService::class.java))
        }
    }
}
