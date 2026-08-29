/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.tv

import android.content.Context
import android.content.Intent
import android.util.Log
import android.provider.Settings as AndroidSettings

/**
 * Which packages are "Settings" on this television.
 *
 * Resolved from the intent rather than hard-coded. `com.android.tv.settings` is what this
 * Philips answers with, and writing that down would be wrong on the first set somebody else
 * tries — the same reasoning as [ScreenSaverPackages] and [TvInputPackages], and the same shape.
 *
 * Resolved once: the answer cannot change while the process lives, and asking the package
 * manager on every foreground change would be work for nothing.
 */
class SettingsPackages(context: Context) {

    private val packages: Set<String> = resolve(context)

    fun contains(packageName: String?): Boolean = packageName != null && packageName in packages

    private fun resolve(context: Context): Set<String> {
        val found = runCatching {
            val intent = Intent(AndroidSettings.ACTION_SETTINGS)
            context.packageManager
                .queryIntentActivities(intent, 0)
                .mapNotNull { it.activityInfo?.packageName }
                .toSet()
        }.getOrElse {
            // An empty set means the block quietly does nothing, so it is said out loud: the
            // alternative is a parent turning a switch on and wondering why it did not work.
            Log.w(EnforcerService.TAG, "settings packages unavailable", it)
            emptySet()
        }
        Log.i(EnforcerService.TAG, "settings packages: ${found.sorted()}")
        return found
    }
}
