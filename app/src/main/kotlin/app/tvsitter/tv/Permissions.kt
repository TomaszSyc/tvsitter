/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.tv

import android.app.AppOpsManager
import android.content.Context
import android.os.Build
import android.os.Process
import android.util.Log
import app.tvsitter.rules.contract.AlertKind
import android.provider.Settings as AndroidSettings

/**
 * The two permissions the whole thing rests on.
 *
 * Both are one Settings screen away for anybody who found the app in the list, and both defeat
 * it silently: without the overlay the lock is an `addView() failed` line in logcat, and without
 * usage access the foreground app is simply never detected — so nothing is counted and nothing
 * is displaced.
 */
object Permissions {

    fun canDrawOverlays(context: Context): Boolean = AndroidSettings.canDrawOverlays(context)

    /**
     * There is no single app-ops call that spans the supported range: `unsafeCheckOpNoThrow`
     * only exists from API 29, and `checkOpNoThrow` is deprecated from that same release.
     * Calling the former unconditionally would throw NoSuchMethodError on Android 8 and 9.
     */
    @Suppress("DEPRECATION")
    fun hasUsageAccess(context: Context): Boolean {
        val appOps = context.getSystemService(AppOpsManager::class.java) ?: return false
        val mode = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            appOps.unsafeCheckOpNoThrow(
                AppOpsManager.OPSTR_GET_USAGE_STATS,
                Process.myUid(),
                context.packageName,
            )
        } else {
            appOps.checkOpNoThrow(
                AppOpsManager.OPSTR_GET_USAGE_STATS,
                Process.myUid(),
                context.packageName,
            )
        }
        return mode == AppOpsManager.MODE_ALLOWED
    }
}

/**
 * Watches both, and says so once when one goes away.
 *
 * Asked where the service is already doing work — building a state payload, sweeping while
 * locked — rather than on a timer of its own: a permission cannot be revoked without somebody
 * being at the television, and that is exactly when those two things are happening anyway.
 *
 * Once per loss, not once per check. The mistake #58 was about is the same one: a condition
 * that stays true turning into a message every few seconds until nobody reads any of them.
 */
class PermissionWatch(private val context: Context, private val onLost: (String) -> Unit) {

    @Volatile
    var canOverlay: Boolean = true
        private set

    @Volatile
    var canUsage: Boolean = true
        private set

    fun check() {
        val overlay = Permissions.canDrawOverlays(context)
        if (!overlay && canOverlay) {
            Log.w(EnforcerService.TAG, "permission: drawing over apps was taken away")
            onLost(AlertKind.OVERLAY_LOST)
        }
        canOverlay = overlay

        val usage = Permissions.hasUsageAccess(context)
        if (!usage && canUsage) {
            Log.w(EnforcerService.TAG, "permission: usage access was taken away")
            onLost(AlertKind.USAGE_LOST)
        }
        canUsage = usage
    }
}
