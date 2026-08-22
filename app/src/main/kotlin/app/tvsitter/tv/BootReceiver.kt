/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.tv

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.os.SystemClock
import android.util.Log

/**
 * Brings the enforcer back after a reboot.
 *
 * This used to be a log marker only, because the system revived the accessibility service by
 * itself — measured at roughly 27 seconds after boot in D13. Since D16 there is no
 * accessibility service, so this is the only thing that restarts enforcement, and the gap it
 * leaves needs measuring again rather than assuming.
 */
class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        // Both are protected broadcasts, but an exported receiver can still be reached by a
        // spoofed intent carrying a different action, or none at all.
        val action = intent.action ?: return

        // Uptime, not wall-clock time: the question is how far into the boot each broadcast
        // arrives, and the wall clock is still being corrected at this point.
        val uptimeSeconds = SystemClock.elapsedRealtime() / MILLIS_PER_SECOND

        when (action) {
            // Measured, not acted on. Whether starting here is worth building depends on how
            // far ahead of BOOT_COMPLETED it lands, and on this hardware that is unknown — a
            // television has no credential lock to wait on, so the two may be moments apart.
            // Starting the enforcer from here would mean everything it persists moving to
            // device-encrypted storage, which is a real change to make on evidence rather
            // than on a hunch. See #23.
            LOCKED_BOOT_COMPLETED -> Log.i(
                EnforcerService.TAG,
                "LOCKED_BOOT_COMPLETED at uptime ${uptimeSeconds}s",
            )

            Intent.ACTION_BOOT_COMPLETED -> {
                Log.i(
                    EnforcerService.TAG,
                    "BOOT_COMPLETED at uptime ${uptimeSeconds}s, starting the enforcer",
                )
                EnforcerService.start(context)
            }
        }
    }

    private companion object {
        // Intent.ACTION_LOCKED_BOOT_COMPLETED is API 24 and available, but naming the string
        // keeps this readable next to the manifest entry it has to match.
        const val LOCKED_BOOT_COMPLETED = "android.intent.action.LOCKED_BOOT_COMPLETED"
        const val MILLIS_PER_SECOND = 1000L
    }
}
