/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.tv

import android.app.AlarmManager
import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.SystemClock
import android.util.Log

/**
 * Brings the enforcer back when the system killed it and did not restart it.
 *
 * `START_STICKY` alone was not enough. Measured on the TA5: the process was killed while a
 * cast YouTube video was playing, and the sticky restart came 32 minutes later, a second after
 * the video stopped — the system holds restarts back while memory is short, which is exactly
 * when the video a child is watching is using it. Half an hour of an unenforced lock.
 *
 * An alarm outlives the process that set it, so a one-shot alarm re-armed on every firing is a
 * pulse the system keeps even when nothing of ours is running. Non-waking: in standby there is
 * nothing to enforce, and an overdue alarm fires the moment the television wakes, which is the
 * moment that matters. A force-stop clears it, and so does a reboot, which `BootReceiver`
 * covers; Home Assistant watches for the first.
 */
class EnforcerWatchdog : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        // Re-armed first: the alarm is one-shot, and a start that throws must not end the chain.
        arm(context)
        if (EnforcerService.instance != null) return
        Log.w(EnforcerService.TAG, "watchdog: the enforcer was not running, starting it")
        // Starting a foreground service from the background is refused on Android 12+ unless an
        // exemption applies. Holding SYSTEM_ALERT_WINDOW is one and an exact alarm is another,
        // but a refusal must cost one pulse, not the receiver.
        runCatching { EnforcerService.start(context) }
            .onFailure { Log.e(EnforcerService.TAG, "watchdog: could not start the enforcer", it) }
    }

    companion object {
        /** How long a killed enforcer can stay dead, at most, while the television is on. */
        private const val PULSE_MS = 60_000L

        /** Arms the next pulse, replacing any already armed. Safe to call repeatedly. */
        fun arm(context: Context) {
            val alarms = context.getSystemService(AlarmManager::class.java) ?: return
            val pulse = PendingIntent.getBroadcast(
                context,
                0,
                Intent(context, EnforcerWatchdog::class.java),
                PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
            )
            val at = SystemClock.elapsedRealtime() + PULSE_MS
            // Exact needs an app-op that setup grants over ADB; without it an inexact alarm may
            // drift by most of a minute, which is still a minute rather than half an hour.
            val exact = Build.VERSION.SDK_INT < Build.VERSION_CODES.S || alarms.canScheduleExactAlarms()
            runCatching {
                if (exact) {
                    alarms.setExactAndAllowWhileIdle(AlarmManager.ELAPSED_REALTIME, at, pulse)
                } else {
                    alarms.setAndAllowWhileIdle(AlarmManager.ELAPSED_REALTIME, at, pulse)
                }
            }.onFailure { Log.e(EnforcerService.TAG, "watchdog: could not arm", it) }
        }
    }
}
