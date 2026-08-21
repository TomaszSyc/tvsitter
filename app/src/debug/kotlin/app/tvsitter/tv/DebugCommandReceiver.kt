/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.tv

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.util.Log

/**
 * Drives the M0 spike from ADB. The component must be addressed explicitly, because a
 * manifest-declared receiver has not received implicit broadcasts since Android 8 — without
 * `-n` the broadcast reports success and runs nothing:
 *
 *   R=app.tvsitter.tv/.DebugCommandReceiver
 *   adb shell am broadcast -n $R -a app.tvsitter.tv.LOCK --es reason "lock test"
 *   adb shell am broadcast -n $R -a app.tvsitter.tv.UNLOCK
 *   adb shell am broadcast -n $R -a app.tvsitter.tv.STATUS
 */
class DebugCommandReceiver : BroadcastReceiver() {

    override fun onReceive(context: Context, intent: Intent) {
        val service = EnforcerService.instance
        if (service == null) {
            Log.w(EnforcerService.TAG, "${intent.action}: accessibility service is not connected")
            return
        }
        when (intent.action) {
            ACTION_LOCK -> service.lock(intent.getStringExtra("reason") ?: "lock test from ADB")
            ACTION_UNLOCK -> service.unlock()
            ACTION_STATUS -> Log.i(
                EnforcerService.TAG,
                "STATUS: locked=${service.isLocked} foreground=${service.foregroundPackage}",
            )
            else -> Log.w(EnforcerService.TAG, "unknown action: ${intent.action}")
        }
    }

    private companion object {
        const val ACTION_LOCK = "app.tvsitter.tv.LOCK"
        const val ACTION_UNLOCK = "app.tvsitter.tv.UNLOCK"
        const val ACTION_STATUS = "app.tvsitter.tv.STATUS"
    }
}
