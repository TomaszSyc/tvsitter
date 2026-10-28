/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.rules

/** One activity answering `CATEGORY_HOME`, with the intent-filter priority it declared. */
data class HomeClaim(val packageName: String, val priority: Int)

/**
 * Which of the packages answering HOME are a home screen the lock must leave alone.
 *
 * Not only the one HOME resolves to: a set can carry several launchers at once (Google's, its
 * setup wizard's, one installed over adb), and whichever of them is on screen must not be sent
 * home by the allow-list.
 *
 * But not every answer either. Android ships `FallbackHome` at a negative priority (Settings
 * declares -1000) so that it shows only when nothing else answers. Counting it while a real
 * launcher exists would exempt Settings from the lock. When nothing else is left, the fallback
 * genuinely is what HOME opens, and then it counts.
 */
object HomeScreens {

    fun of(claims: Iterable<HomeClaim>): Set<String> {
        val real = claims.filter { it.priority >= 0 }
        return (real.ifEmpty { claims.toList() }).mapTo(mutableSetOf()) { it.packageName }
    }
}
