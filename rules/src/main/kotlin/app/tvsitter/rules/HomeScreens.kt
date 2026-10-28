/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.rules

/**
 * One activity answering `CATEGORY_HOME`: the intent-filter priority it declared, and whether it
 * came with the firmware.
 */
data class HomeClaim(val packageName: String, val priority: Int, val system: Boolean)

/**
 * Which of the packages answering HOME are a home screen the lock must leave alone.
 *
 * Not only the one HOME resolves to: a set carries several launchers at once (Google's, its setup
 * wizard's), and whichever of them is on screen must not be sent home by the allow-list. Those
 * come with the firmware. An installed launcher counts only once it is [chosen][of] as home,
 * because declaring HOME costs an app one intent filter, and that alone must not walk a player
 * past the allow-list, the budgets and the lock. Choosing it takes Settings or adb.
 *
 * Fallbacks never count while anything real is left. Android ships `FallbackHome` at a negative
 * priority (Settings declares -1000) so that it shows only when nothing else answers; counting it
 * would exempt Settings from the lock. When nothing real is left, the fallback genuinely is what
 * HOME opens, and then it counts.
 */
object HomeScreens {

    /** [chosen] is the package HOME resolves to right now; the chooser resolves to `android`. */
    fun of(claims: Iterable<HomeClaim>, chosen: String?): Set<String> {
        val (real, fallbacks) = claims.partition { it.priority >= 0 }
        val home = real.filter { it.system || it.packageName == chosen }
        return home.ifEmpty { fallbacks }.mapTo(mutableSetOf()) { it.packageName }
    }
}
