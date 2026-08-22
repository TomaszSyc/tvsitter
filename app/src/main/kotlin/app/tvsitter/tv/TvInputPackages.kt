/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.tv

import android.content.Context
import android.content.Intent
import android.media.tv.TvInputService
import android.util.Log

/**
 * Which packages are television or HDMI inputs, so their time is always charged.
 *
 * An input is an ordinary activity here (D12) and its sound does reach Android through the
 * set's input service — measured with a console on HDMI. But that is one television's
 * behaviour rather than a promise, and of the two ways to be wrong, a console session costing
 * a child nothing is much worse than a menu counted for a few extra minutes. So an input
 * counts whenever the screen is on, without asking whether anything is playing.
 *
 * Resolved by asking which packages provide a [TvInputService], the same way screen savers are
 * found by asking for a `DreamService` (D20), and for the same reason: `org.droidtv.playtv` is
 * what this Philips happens to use, and a hard-coded name would be wrong on any other set with
 * nothing to say so.
 */
class TvInputPackages(context: Context) {

    private val packages: Set<String> = resolve(context)

    fun contains(packageName: String?): Boolean = packageName != null && packageName in packages

    private fun resolve(context: Context): Set<String> {
        val found = runCatching {
            context.packageManager
                .queryIntentServices(Intent(TvInputService.SERVICE_INTERFACE), 0)
                .mapNotNull { it.serviceInfo?.packageName }
                .toSet()
        }.getOrElse {
            Log.w(EnforcerService.TAG, "could not list TV inputs; none will be privileged", it)
            emptySet()
        }

        // Logged for the same reason as the screen savers: an empty set is silent and changes
        // the accounting, and this line is the only place it would show.
        Log.i(EnforcerService.TAG, "tv inputs: ${found.sorted()}")
        return found
    }
}
