/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.rules

import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Test

class HomeScreensTest {

    private val launcherx = HomeClaim("com.google.android.apps.tv.launcherx", 2, system = true)
    private val setupwraith = HomeClaim("com.google.android.tungsten.setupwraith", 1, system = true)
    private val settings = HomeClaim("com.android.tv.settings", -1000, system = true)
    private val realtek = HomeClaim("com.realtek.systemservice", -999, system = true)
    private val installed = HomeClaim("com.example.launcher", 0, system = false)

    @Test
    fun `fallbacks are not home while a real launcher exists`() {
        // Settings answers HOME with its FallbackHome. Counting it as a home screen would exempt
        // Settings from the lock, and the Settings block would lose half of what it does.
        assertEquals(
            setOf(launcherx.packageName, setupwraith.packageName),
            HomeScreens.of(listOf(launcherx, setupwraith, settings, realtek), chosen = launcherx.packageName),
        )
    }

    @Test
    fun `an installed launcher nobody chose is not a home screen`() {
        // Declaring HOME costs an app one intent filter. Were that enough, any player that also
        // calls itself a launcher would walk past the allow-list, the budgets and the lock.
        assertEquals(
            setOf(launcherx.packageName),
            HomeScreens.of(listOf(launcherx, installed), chosen = launcherx.packageName),
        )
    }

    @Test
    fun `the installed launcher chosen as home is a home screen`() {
        // Choosing it takes Settings or adb, which is a parent's decision.
        assertEquals(
            setOf(launcherx.packageName, installed.packageName),
            HomeScreens.of(listOf(launcherx, installed, settings), chosen = installed.packageName),
        )
    }

    @Test
    fun `with only fallbacks the fallback is the home screen`() {
        // Every real launcher disabled: HOME then really opens the fallback, and sending it home
        // would be a fight with itself.
        assertEquals(
            setOf(settings.packageName),
            HomeScreens.of(listOf(settings), chosen = settings.packageName),
        )
    }

    @Test
    fun `an unchosen installed launcher does not stand in for a missing system one`() {
        // No system launcher left and nothing chosen: HOME opens the chooser, which is the
        // system's. The fallback is home; the installed launcher still has to be chosen.
        assertEquals(
            setOf(settings.packageName),
            HomeScreens.of(listOf(installed, settings), chosen = "android"),
        )
    }

    @Test
    fun `no claims means no home screen`() {
        assertEquals(emptySet<String>(), HomeScreens.of(emptyList(), chosen = null))
    }

    @Test
    fun `a package with two home activities is one home screen`() {
        val claims = listOf(HomeClaim("x", 0, system = true), HomeClaim("x", 1, system = true))
        assertEquals(setOf("x"), HomeScreens.of(claims, chosen = null))
    }
}
