/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.rules

import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Test

class TrustedTimeTest {

    private val hour = 3_600_000L
    private val real = 1_791_700_000_000L

    @Test
    fun `network time setting the clock after a cold boot is believed`() {
        // What the television did: it booted with a clock three days slow, the app read it,
        // and the network put it right a minute later. Treating that as somebody moving the
        // clock left the budget day three days behind, and nothing rolled over.
        val jumps = mutableListOf<Long>()
        val time = TrustedTime { jumps += it }
        time.now(wallMs = real - 74 * hour, elapsedMs = 40_000, networkTime = true)

        val after = time.now(wallMs = real + 60_000, elapsedMs = 100_000, networkTime = true)

        assertEquals(real + 60_000, after)
        assertEquals(emptyList<Long>(), jumps)
    }

    @Test
    fun `a clock set back by hand is still ignored`() {
        val jumps = mutableListOf<Long>()
        val time = TrustedTime { jumps += it }
        time.now(wallMs = real, elapsedMs = 1_000_000, networkTime = false)

        val after = time.now(wallMs = real - 2 * hour + 10_000, elapsedMs = 1_010_000, networkTime = false)

        assertEquals(real + 10_000, after)
        assertEquals(listOf(-2 * hour), jumps)
    }

    @Test
    fun `turning network time back on drops what was set by hand`() {
        val time = TrustedTime()
        time.now(wallMs = real, elapsedMs = 1_000_000, networkTime = false)
        time.now(wallMs = real - 2 * hour, elapsedMs = 1_000_000, networkTime = false)

        val after = time.now(wallMs = real + 5_000, elapsedMs = 1_005_000, networkTime = true)

        assertEquals(real + 5_000, after)
    }

    @Test
    fun `ordinary drift inside the slack is not a jump`() {
        val jumps = mutableListOf<Long>()
        val time = TrustedTime { jumps += it }
        time.now(wallMs = real, elapsedMs = 1_000_000, networkTime = false)

        val after = time.now(wallMs = real + 10_000 + 30_000, elapsedMs = 1_010_000, networkTime = false)

        assertEquals(real + 40_000, after)
        assertEquals(emptyList<Long>(), jumps)
    }
}
