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
 * For now just a log marker: we want to see the ordering of events after the TV reboots —
 * whether the accessibility service comes back on its own, and whether it does so before
 * BOOT_COMPLETED.
 */
class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        // BOOT_COMPLETED is a protected broadcast, but an exported receiver can still be
        // reached by a spoofed intent carrying a different action, or none at all.
        if (intent.action != Intent.ACTION_BOOT_COMPLETED) return

        Log.i(
            EnforcerService.TAG,
            "BOOT_COMPLETED, service connected=${EnforcerService.instance != null}",
        )
    }
}
