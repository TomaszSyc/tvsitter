/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.tv

import android.app.Service
import android.content.Intent
import android.os.Build
import android.os.IBinder
import android.util.Log
import app.tvsitter.rules.contract.Command
import app.tvsitter.rules.contract.StateSnapshot
import app.tvsitter.rules.pairing.PairRequest
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
    private var telemetry: Telemetry? = null
    private var screenTime: ScreenTimeTracker? = null
    private var activeRules: ActiveRules? = null
    private var pairing: PairingManager? = null

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)

    val foregroundPackage: String? get() = foregroundApps?.current

    val isLocked: Boolean get() = overlay?.isShowing == true

    val pairingPin: String? get() = pairing?.pin

    /** Whether this TV has broker settings, which is the lasting result of pairing. */
    val isPaired: Boolean get() = telemetry?.isConfigured == true

    /** Whether it is actually reaching the broker, as opposed to merely being configured. */
    val isReporting: Boolean get() = telemetry?.isConnected == true

    /**
     * Whether the last attempt to open a pairing window failed to get as far as advertising.
     *
     * Only worth reading when there is no PIN: a window that opened says so by itself. Without
     * this the setup screen cannot distinguish "press the button" from "the button did not
     * work", and both looked identical.
     */
    var lastPairingFailed: Boolean = false
        private set

    fun pairingSecondsRemaining(): Long = pairing?.secondsRemaining() ?: 0

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        instance = this
        EnforcerNotification.attach(this)

        overlay = LockOverlay(this)
        appLabels = AppLabels(this)
        screenTime = ScreenTimeTracker(this, onDayRolled = { telemetry?.publishSoon() })
        activeRules = ActiveRules(this).also { rules -> scope.launch { rules.load() } }
        // Commands arrive on an RxJava thread owned by the MQTT client, and acting on one
        // touches the window manager, where addView from any thread but the main one throws.
        // That is why locking from Home Assistant failed every time while the same lock
        // through the debug ADB hook worked: that one arrives via onStartCommand, which is
        // already on the main thread. `scope` is Dispatchers.Main.immediate.
        telemetry = Telemetry(this, scope, ::currentState) { command ->
            scope.launch { handleCommand(command) }
        }
        foregroundApps = ForegroundAppMonitor(this) { pkg ->
            screenTime?.sampleAtTransition(screenState?.isScreenOn == true, pkg)
            telemetry?.publishSoon()
        }.also { it.start(scope) { screenState?.isScreenOn != false } }
        screenState = ScreenState(this) { on ->
            screenTime?.sampleAtTransition(on, foregroundApps?.current)
            telemetry?.publishSoon()
        }.also { it.start() }
        screenTime?.start(
            scope,
            screenOn = { screenState?.isScreenOn == true },
            appId = { foregroundApps?.current },
        )

        Log.i(
            TAG,
            "onCreate(): version=${BuildConfig.VERSION_NAME} api=${Build.VERSION.SDK_INT} " +
                "model=${Build.MODEL} manufacturer=${Build.MANUFACTURER}",
        )

        scope.launch { startTelemetryOrOfferPairing() }
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_LOCK -> lock(intent.getStringExtra(EXTRA_REASON))
            ACTION_UNLOCK -> unlock()
        }
        // Sticky because there is no longer anything else to bring this back: if the system
        // kills the process, restarting it is the only way the counter resumes.
        return START_STICKY
    }

    fun lock(reason: String?) {
        overlay?.show(
            title = getString(R.string.lock_title),
            // A reason that only repeats the title would print the same sentence twice on a
            // fifty-inch screen. A plain `lock` with no reason gets no second line.
            subtitle = reason?.takeIf { it.isNotBlank() && it != getString(R.string.lock_title) },
            onAskForTime = { Log.i(TAG, "TODO M3: request for more time") },
        )
        telemetry?.publishSoon()
    }

    fun unlock() {
        overlay?.hide()
        telemetry?.publishSoon()
    }

    /**
     * An unconfigured TV offers itself for pairing rather than sitting there doing nothing.
     * That is the point of D14: a fresh install is discoverable with no setup at all, and
     * Home Assistant finds it on its own.
     */
    private suspend fun startTelemetryOrOfferPairing() {
        if (telemetry?.start() == true) return
        Log.i(TAG, "no broker configured, offering pairing")
        startPairing(Settings(this).deviceId())
    }

    /** Reconnects with whatever settings are now stored. Used by the debug configure hook. */
    fun reloadTelemetry() {
        telemetry?.restart()
    }

    /**
     * Starts pairing without the caller having to resolve the device id first, which would
     * otherwise mean a storage read on whatever thread pressed the button.
     */
    fun requestPairing() {
        scope.launch { startPairing(Settings(this@EnforcerService).deviceId()) }
    }

    /** Opens a pairing window and returns the PIN to display, or null if it could not start. */
    fun startPairing(deviceId: String): String? {
        pairing?.stop()
        val manager = PairingManager(this, deviceId, ::onPaired)
        pairing = manager
        val pin = manager.start()
        lastPairingFailed = pin == null
        return pin
    }

    /** Runs on the pairing server's thread, so the storage write is handed to a coroutine. */
    private fun onPaired(request: PairRequest) {
        scope.launch {
            Settings(this@EnforcerService).updateBroker { current ->
                current.copy(
                    host = request.host,
                    port = request.port,
                    username = request.username,
                    password = request.password,
                    topicPrefix = request.topicPrefix,
                    useTls = request.useTls,
                )
            }
            Log.i(TAG, "paired with ${request.host}:${request.port}, prefix ${request.topicPrefix}")
            telemetry?.restart()
        }
    }

    private fun handleCommand(command: Command) {
        when (command) {
            is Command.Lock -> lock(command.reason)
            is Command.Unlock -> unlock()
            is Command.Ping -> telemetry?.publishSoon()
            is Command.StopApp -> Log.i(TAG, "TODO M2: stop ${command.pkg}")
            is Command.Grant, is Command.Deny -> Log.i(TAG, "TODO M3: $command")
            is Command.SetRules -> scope.launch {
                activeRules?.apply(command.rules, command.rev)
                telemetry?.publishSoon()
            }
        }
    }

    /** The single place that says what the current state is; Telemetry decides when to send it. */
    private fun currentState(): StateSnapshot {
        val pkg = foregroundApps?.current
        val limitSeconds = activeRules?.dailyLimitSeconds
        return StateSnapshot(
            ts = System.currentTimeMillis(),
            fw = BuildConfig.VERSION_NAME,
            screenOn = screenState?.isScreenOn ?: false,
            locked = isLocked,
            appId = pkg,
            appName = pkg?.let { appLabels?.labelOf(it) },
            usedTodaySeconds = screenTime?.usedSeconds ?: 0,
            bonusTodaySeconds = screenTime?.bonusSeconds ?: 0,
            perApp = screenTime?.perAppSeconds ?: emptyMap(),
            // Published rather than assumed: this TV keeps its own rules and enforces them
            // offline (D3), so it is the only thing that knows what is actually in force.
            limitTodaySeconds = limitSeconds?.toInt(),
            remainingTodaySeconds = screenTime?.remainingSeconds(limitSeconds),
            rulesRev = activeRules?.revision ?: 0,
        )
    }

    override fun onDestroy() {
        Log.w(TAG, "onDestroy(): the enforcer is going down")
        telemetry?.stop()
        telemetry = null
        pairing?.stop()
        pairing = null
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

        @Volatile
        var instance: EnforcerService? = null
            private set

        /** Starts the service if it is not already running. Safe to call repeatedly. */
        fun start(context: android.content.Context) {
            context.startForegroundService(Intent(context, EnforcerService::class.java))
        }
    }
}
