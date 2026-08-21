/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.tv

import android.content.Context
import android.content.pm.PackageManager
import android.util.Log
import java.util.concurrent.ConcurrentHashMap

/**
 * Turns `com.netflix.ninja` into "Netflix".
 *
 * Cached, because a label lookup goes through the package manager and the foreground
 * package changes often enough that doing it every time is waste. Unresolvable packages are
 * cached too — a missing app should not mean a lookup on every event.
 */
class AppLabels(context: Context) {

    private val packageManager: PackageManager = context.packageManager
    private val cache = ConcurrentHashMap<String, String>()

    /** The human label, or the package name itself when nothing better is available. */
    fun labelOf(packageId: String): String = cache.getOrPut(packageId) {
        runCatching {
            packageManager.getApplicationLabel(
                packageManager.getApplicationInfo(packageId, 0),
            ).toString()
        }.getOrElse {
            Log.d(EnforcerService.TAG, "no label for $packageId, falling back to the id")
            packageId
        }
    }

    fun clear() = cache.clear()
}
