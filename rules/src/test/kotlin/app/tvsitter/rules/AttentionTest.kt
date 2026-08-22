/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.rules

import org.junit.jupiter.api.Assertions.assertFalse
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test

class AttentionTest {

    private val watching = Attention(
        screenOn = true,
        screenSaver = false,
        playing = true,
        tvInput = false,
        quietForMs = 0,
    )

    @Test
    fun `a film counts`() {
        assertTrue(AttentionRule.isWatching(watching))
    }

    @Test
    fun `a dark screen never counts`() {
        assertFalse(AttentionRule.isWatching(watching.copy(screenOn = false)))
    }

    @Test
    fun `a screen saver never counts, even with sound`() {
        // D20's case. Some screen savers play music, and a room nobody is in should not pay
        // for it.
        assertFalse(AttentionRule.isWatching(watching.copy(screenSaver = true)))
    }

    @Test
    fun `browsing counts for a while, and then stops`() {
        val browsing = watching.copy(playing = false)

        assertTrue(
            AttentionRule.isWatching(browsing.copy(quietForMs = AttentionRule.GRACE_MS - 1)),
            "choosing a programme is television time",
        )
        assertFalse(
            AttentionRule.isWatching(browsing.copy(quietForMs = AttentionRule.GRACE_MS)),
            "a set left on the launcher at dinner is not",
        )
    }

    @Test
    fun `the seven minutes that started this`() {
        // Measured: the TV's own image-sticking protection over a static screen, billed to the
        // day. Nothing plays, nothing changes, and the screen stays on the whole time.
        val idle = watching.copy(playing = false, quietForMs = 7 * 60 * 1000)

        assertFalse(AttentionRule.isWatching(idle))
    }

    @Test
    fun `a console counts even when Android hears nothing`() {
        // On this set an HDMI source does reach the mixer, but that is one television's
        // behaviour rather than a promise. A console session costing nothing is the worse
        // failure of the two, so an input always counts while the screen is on.
        val console = watching.copy(
            playing = false,
            tvInput = true,
            quietForMs = 60 * 60 * 1000,
        )

        assertTrue(AttentionRule.isWatching(console))
    }

    @Test
    fun `an input still does not count with the screen off`() {
        assertFalse(AttentionRule.isWatching(watching.copy(tvInput = true, screenOn = false)))
    }

    @Test
    fun `playing keeps counting however long it goes on`() {
        // The grace period must not expire under a two-hour film, which it would if quiet
        // time were the only test.
        assertTrue(AttentionRule.isWatching(watching.copy(quietForMs = 2 * 60 * 60 * 1000)))
    }
}
