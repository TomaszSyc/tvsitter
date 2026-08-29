/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.rules

import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Test

class ClockWatchTest {

    private val minute = 60_000L
    private val hour = 60 * minute

    @Test
    fun `two clocks that agree have nothing to report`() {
        assertEquals(0, ClockWatch.jumpBetween(wallDeltaMs = 10_000, elapsedDeltaMs = 10_000))
    }

    @Test
    fun `a late tick is not an attack`() {
        // A device coming out of doze delivers one, and calling that tampering would cry wolf
        // on an ordinary morning.
        assertEquals(0, ClockWatch.jumpBetween(wallDeltaMs = 70_000, elapsedDeltaMs = 10_000))
    }

    @Test
    fun `an hour appearing out of nowhere is the clock, not time passing`() {
        val jump = ClockWatch.jumpBetween(wallDeltaMs = hour + 10_000, elapsedDeltaMs = 10_000)

        assertEquals(hour, jump)
    }

    @Test
    fun `going backwards counts too`() {
        // Forward buys a fresh day. Backwards keeps the old one from ever ending, which is the
        // same trick from the other side.
        val jump = ClockWatch.jumpBetween(wallDeltaMs = -hour, elapsedDeltaMs = 10_000)

        assertEquals(-hour - 10_000, jump)
    }

    @Test
    fun `the boundary is where it is documented`() {
        val slack = ClockWatch.SLACK_MS
        assertEquals(0, ClockWatch.jumpBetween(slack + 10_000, 10_000), "exactly the slack")
        assertEquals(slack + 1, ClockWatch.jumpBetween(slack + 10_001, 10_000), "one past it")
    }

    @Test
    fun `the correction accumulates, because somebody can move it twice`() {
        val wall = 1_787_400_000_000

        val once = ClockWatch.trusted(wall, offsetMs = hour)
        val twice = ClockWatch.trusted(wall, offsetMs = 2 * hour)

        assertEquals(wall - hour, once)
        assertEquals(wall - 2 * hour, twice)
    }

    @Test
    fun `no jump means the clock is taken at its word`() {
        val wall = 1_787_400_000_000

        assertEquals(wall, ClockWatch.trusted(wall, offsetMs = 0))
    }
}
