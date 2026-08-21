/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.tv

import android.accessibilityservice.AccessibilityService
import android.content.Intent
import android.os.Build
import android.util.Log
import android.view.KeyEvent
import android.view.accessibility.AccessibilityEvent

/**
 * The heart of the app. An accessibility service is used here for two reasons:
 *  1. it is the only root-free source of "which app is in the foreground right now",
 *  2. it may draw its own window ([LockOverlay]) on top of someone else's app without
 *     the SYSTEM_ALERT_WINDOW permission, which frequently cannot be granted from the
 *     UI on Google TV.
 *
 * The system also restarts accessibility services after a reboot and after the process
 * is killed — which is why the screen time counter lives here rather than in an
 * ordinary foreground service.
 */
class EnforcerService : AccessibilityService() {

    @Volatile
    var foregroundPackage: String? = null
        private set

    private var overlay: LockOverlay? = null

    val isLocked: Boolean
        get() = overlay?.isShowing == true

    override fun onServiceConnected() {
        super.onServiceConnected()
        instance = this
        overlay = LockOverlay(this)
        Log.i(
            TAG,
            "onServiceConnected(): version=${BuildConfig.VERSION_NAME} api=${Build.VERSION.SDK_INT} " +
                "model=${Build.MODEL} manufacturer=${Build.MANUFACTURER}",
        )
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent) {
        if (event.eventType != AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED) return
        val pkg = event.packageName?.toString() ?: return
        if (pkg == packageName) return

        if (pkg != foregroundPackage) {
            foregroundPackage = pkg
            Log.i(TAG, "foreground=$pkg class=${event.className}")
        }

        // A new window may have appeared above ours, so push the lock back to the front.
        if (isLocked) overlay?.reassert()
    }

    /**
     * Remote key filtering. The open question this answers is whether HOME can be
     * intercepted at all — it is the one key an ordinary window cannot stop. Everything
     * else has to pass through, otherwise our own lock screen becomes unusable
     * (D-pad, ENTER).
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
        overlay?.show(
            title = getString(R.string.lock_title),
            subtitle = reason,
            onAskForTime = { Log.i(TAG, "TODO M3: request for more time") },
        )
    }

    fun unlock() {
        overlay?.hide()
    }

    override fun onInterrupt() = Unit

    override fun onUnbind(intent: Intent?): Boolean {
        Log.w(TAG, "onUnbind(): service detached — accessibility was turned off or the system killed us")
        overlay?.hide()
        overlay = null
        instance = null
        return super.onUnbind(intent)
    }

    companion object {
        const val TAG = "TVSitter"

        /** Accessibility services are singletons; the UI and ADB test hooks need a handle. */
        @Volatile
        var instance: EnforcerService? = null
            private set
    }
}
