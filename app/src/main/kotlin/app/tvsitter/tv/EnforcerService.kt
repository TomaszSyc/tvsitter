/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.tv

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.AccessibilityServiceInfo
import android.content.Intent
import android.os.Build
import android.util.Log
import android.view.KeyEvent
import android.view.accessibility.AccessibilityEvent
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
 * The heart of the app. An accessibility service is used here for two reasons:
 *  1. it is the only root-free source of "which app is in the foreground right now",
 *  2. it may draw its own window ([LockOverlay]) on top of someone else's app without
 *     the SYSTEM_ALERT_WINDOW permission, which frequently cannot be granted from the
 *     UI on Google TV.
 *
 * The system also restarts accessibility services after a reboot and after the process
 * is killed — measured at roughly 27 seconds after boot on the target hardware, before
 * BOOT_COMPLETED — which is why the screen time counter lives here rather than in an
 * ordinary foreground service.
 */
class EnforcerService : AccessibilityService() {

    @Volatile
    var foregroundPackage: String? = null
        private set

    private var overlay: LockOverlay? = null
    private var screenState: ScreenState? = null
    private var appLabels: AppLabels? = null
    private var mqtt: MqttBridge? = null

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)
    private var pendingPublish: Job? = null

    val isLocked: Boolean
        get() = overlay?.isShowing == true

    override fun onServiceConnected() {
        super.onServiceConnected()
        instance = this
        overlay = LockOverlay(this)
        appLabels = AppLabels(this)
        screenState = ScreenState(this) { publishSoon() }.also { it.start() }

        Log.i(
            TAG,
            "onServiceConnected(): version=${BuildConfig.VERSION_NAME} api=${Build.VERSION.SDK_INT} " +
                "model=${Build.MODEL} manufacturer=${Build.MANUFACTURER}",
        )

        // Key filtering off until the lock actually needs it. The capability is declared in
        // the service config so the user consents to it once and HOME stays interceptable,
        // but a service receiving every keystroke is a keylogger by capability, and there is
        // no reason for that to be live while nobody is locked out.
        setKeyFiltering(enabled = false)

        scope.launch { startMqtt() }
        scope.launch { heartbeat() }
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent) {
        if (event.eventType != AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED) return
        val pkg = event.packageName?.toString() ?: return
        if (pkg == packageName) return

        if (pkg != foregroundPackage) {
            foregroundPackage = pkg
            Log.i(TAG, "foreground=$pkg class=${event.className}")
            publishSoon()
        }

        // A new window may have appeared above ours, so push the lock back to the front.
        if (isLocked) overlay?.reassert()
    }

    /**
     * Remote key filtering. HOME is the one key an ordinary window cannot stop, and on the
     * target hardware it is genuinely swallowed here — but only for events from a real
     * remote. Injected events (`adb shell input keyevent`) bypass this callback entirely,
     * so an ADB-driven test reports a false negative.
     *
     * Everything else must pass through, otherwise the lock screen's own controls die.
     */
    override fun onKeyEvent(event: KeyEvent): Boolean {
        if (!isLocked) return false
        if (event.action != KeyEvent.ACTION_DOWN) return false

        Log.d(TAG, "onKeyEvent while locked: ${KeyEvent.keyCodeToString(event.keyCode)}")
        return when (event.keyCode) {
            KeyEvent.KEYCODE_HOME,
            KeyEvent.KEYCODE_APP_SWITCH,
            KeyEvent.KEYCODE_SETTINGS,
            -> true
            else -> false
        }
    }

    fun lock(reason: String) {
        setKeyFiltering(enabled = true)
        overlay?.show(
            title = getString(R.string.lock_title),
            subtitle = reason,
            onAskForTime = { Log.i(TAG, "TODO M3: request for more time") },
        )
        publishSoon()
    }

    fun unlock() {
        overlay?.hide()
        setKeyFiltering(enabled = false)
        publishSoon()
    }

    /**
     * Turns key filtering on and off at runtime.
     *
     * The declared flag is what makes [onKeyEvent] fire at all, so clearing it means the
     * service stops seeing keystrokes entirely rather than merely ignoring them.
     */
    private fun setKeyFiltering(enabled: Boolean) {
        val info = serviceInfo ?: return
        val flag = AccessibilityServiceInfo.FLAG_REQUEST_FILTER_KEY_EVENTS
        val updated = if (enabled) info.flags or flag else info.flags and flag.inv()
        if (updated == info.flags) return

        info.flags = updated
        runCatching { serviceInfo = info }
            .onSuccess { Log.i(TAG, "key filtering ${if (enabled) "on" else "off"}") }
            .onFailure { Log.w(TAG, "could not change key filtering", it) }
    }

    /** Drops any existing connection and reconnects with whatever is now stored. */
    fun reconnectMqtt() {
        scope.launch {
            mqtt?.disconnect()
            mqtt = null
            startMqtt()
        }
    }

    private suspend fun startMqtt() {
        val config = Settings(this).broker.first()
        if (!config.isComplete) {
            Log.w(TAG, "mqtt: not configured, nothing will be published (see tools/device.sh configure)")
            return
        }
        mqtt = MqttBridge(config, ::handleCommand).also { it.connect() }
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
     * Window transitions arrive in bursts — opening one app can produce several within a
     * few hundred milliseconds — so publishes are coalesced rather than sent per event.
     */
    private fun publishSoon() {
        pendingPublish?.cancel()
        pendingPublish = scope.launch {
            delay(PUBLISH_DEBOUNCE_MS)
            publishNow()
        }
    }

    /**
     * Republishes on a timer even when nothing changed, so that `ts` stays fresh and a
     * consumer can tell a quiet TV from a stale retained payload.
     */
    private suspend fun heartbeat() {
        while (scope.isActive) {
            delay(HEARTBEAT_MS)
            publishNow()
        }
    }

    private fun publishNow() {
        val bridge = mqtt ?: return
        val pkg = foregroundPackage
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

    override fun onInterrupt() = Unit

    override fun onUnbind(intent: Intent?): Boolean {
        Log.w(TAG, "onUnbind(): service detached — accessibility was turned off or the system killed us")
        mqtt?.disconnect()
        mqtt = null
        screenState?.stop()
        screenState = null
        overlay?.hide()
        overlay = null
        appLabels = null
        instance = null
        scope.cancel()
        return super.onUnbind(intent)
    }

    companion object {
        const val TAG = "TVSitter"

        private const val PUBLISH_DEBOUNCE_MS = 400L
        private const val HEARTBEAT_MS = 60_000L

        /** Accessibility services are singletons; the UI and ADB test hooks need a handle. */
        @Volatile
        var instance: EnforcerService? = null
            private set
    }
}
