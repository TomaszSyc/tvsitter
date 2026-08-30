/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.tv

import android.content.Context
import android.content.Intent
import android.service.dreams.DreamService
import android.util.Log

/**
 * Which packages are screen savers, so their time is not charged to anybody.
 *
 * A dream runs with the panel lit and the room empty, and Android does not send
 * `ACTION_SCREEN_OFF` for it — so without this the counter spends a child's evening while
 * nobody is watching. See D20.
 *
 * Resolved by asking which packages provide a [DreamService] rather than by naming the Google
 * TV one. `com.google.android.apps.tv.dreamx` is what this particular television happens to
 * use; another set would use its own, and a hard-coded name would be wrong there and nowhere
 * would say so.
 */
class ScreenSaverPackages(context: Context) {

    private val packages: Set<String> = resolve(context)

    fun contains(packageName: String?): Boolean = packageName != null && packageName in packages

    /** The whole set, for the state payload that tells Home Assistant what it cannot rule on. */
    val all: Set<String> get() = packages

    private fun resolve(context: Context): Set<String> {
        val found = runCatching {
            context.packageManager
                .queryIntentServices(Intent(DreamService.SERVICE_INTERFACE), 0)
                .mapNotNull { it.serviceInfo?.packageName }
                .toSet()
        }.getOrElse {
            Log.w(EnforcerService.TAG, "could not list screen savers; none will be excluded", it)
            emptySet()
        }

        // Logged because an empty set is silent and wrong: it means every screen saver counts
        // as viewing, and the only way to notice is to read this line.
        Log.i(EnforcerService.TAG, "screen savers: ${found.sorted()}")
        return found
    }
}
