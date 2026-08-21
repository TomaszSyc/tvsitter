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
 * Brings the enforcer back after a reboot.
 *
 * This used to be a log marker only, because the system revived the accessibility service by
 * itself — measured at roughly 27 seconds after boot in D13. Since D16 there is no
 * accessibility service, so this is the only thing that restarts enforcement, and the gap it
 * leaves needs measuring again rather than assuming.
 */
class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        // BOOT_COMPLETED is a protected broadcast, but an exported receiver can still be
        // reached by a spoofed intent carrying a different action, or none at all.
        if (intent.action != Intent.ACTION_BOOT_COMPLETED) return

        Log.i(EnforcerService.TAG, "BOOT_COMPLETED, starting the enforcer")
        EnforcerService.start(context)
    }
}
