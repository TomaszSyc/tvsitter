/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.rules

import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Test

class HomeScreensTest {

    @Test
    fun `fallbacks are not home while a real launcher exists`() {
        // Settings answers HOME with its FallbackHome. Counting it as a home screen would exempt
        // Settings from the lock, and the Settings block would lose half of what it does.
        val claims = listOf(
            HomeClaim("com.google.android.apps.tv.launcherx", 2),
            HomeClaim("com.google.android.tungsten.setupwraith", 1),
            HomeClaim("com.gathin.tvhome", 0),
            HomeClaim("com.android.tv.settings", -1000),
            HomeClaim("com.realtek.systemservice", -999),
        )

        assertEquals(
            setOf(
                "com.google.android.apps.tv.launcherx",
                "com.google.android.tungsten.setupwraith",
                "com.gathin.tvhome",
            ),
            HomeScreens.of(claims),
        )
    }

    @Test
    fun `with only fallbacks the fallback is the home screen`() {
        // Every real launcher disabled: HOME then really opens the fallback, and sending it home
        // would be a fight with itself.
        assertEquals(
            setOf("com.android.tv.settings"),
            HomeScreens.of(listOf(HomeClaim("com.android.tv.settings", -1000))),
        )
    }

    @Test
    fun `no claims means no home screen`() {
        assertEquals(emptySet<String>(), HomeScreens.of(emptyList()))
    }

    @Test
    fun `a package with two home activities is one home screen`() {
        assertEquals(setOf("x"), HomeScreens.of(listOf(HomeClaim("x", 0), HomeClaim("x", 1))))
    }
}
