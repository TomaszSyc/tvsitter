/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.rules

import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertFalse
import org.junit.jupiter.api.Assertions.assertNull
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.ZoneId

class ScreenTimeCounterTest {

    private val warsaw = ZoneId.of("Europe/Warsaw")
    private val clock = BudgetClock(warsaw, dayStartHour = 4)
    private val counter = ScreenTimeCounter(clock)

    private fun at(text: String): Long = LocalDateTime.parse(text).atZone(warsaw).toInstant().toEpochMilli()

    private fun day(text: String): LocalDate = LocalDate.parse(text)

    private fun fresh(text: String) = BudgetState(day = day(text))

    @Test
    fun `the first sample only plants an anchor`() {
        val result = counter.sample(fresh("2026-08-22"), at("2026-08-22T20:00:00"), watching = true)

        assertEquals(0, result.addedMillis)
        assertEquals(0, result.state.usedMillis)
        assertEquals(at("2026-08-22T20:00:00"), result.state.lastSampleAtMs)
    }

    @Test
    fun `a watched interval counts for exactly its length`() {
        val anchored = fresh("2026-08-22").copy(lastSampleAtMs = at("2026-08-22T20:00:00"))

        val result = counter.sample(anchored, at("2026-08-22T20:00:10"), watching = true)

        assertEquals(10_000, result.addedMillis)
        assertEquals(10, result.state.usedSeconds)
    }

    @Test
    fun `an interval with the screen off counts for nothing but still re-anchors`() {
        val anchored = fresh("2026-08-22").copy(
            usedMillis = 60_000,
            lastSampleAtMs = at("2026-08-22T20:00:00"),
        )

        val result = counter.sample(anchored, at("2026-08-22T20:00:10"), watching = false)

        assertEquals(0, result.addedMillis)
        assertEquals(60_000, result.state.usedMillis)
        assertEquals(at("2026-08-22T20:00:10"), result.state.lastSampleAtMs)
    }

    @Test
    fun `an interval longer than the clamp is discarded rather than invented`() {
        val anchored = fresh("2026-08-22").copy(lastSampleAtMs = at("2026-08-22T20:00:00"))

        // The TV suspended and sampling stopped. Believing this would add three hours nobody
        // watched, which is the failure the clamp exists for.
        val result = counter.sample(anchored, at("2026-08-22T23:00:00"), watching = true)

        assertEquals(0, result.addedMillis)
        assertEquals(3 * 3_600_000L, result.discardedMillis)
        assertEquals(0, result.state.usedMillis)
    }

    @Test
    fun `a long interval known not to be watched is not a gap`() {
        val anchored = fresh("2026-08-22").copy(lastSampleAtMs = at("2026-08-22T22:00:00"))

        // A night of standby. We know nobody watched, so there is nothing to reconcile and
        // nothing to report — reporting it would drown the real gaps in noise.
        val result = counter.sample(anchored, at("2026-08-23T03:00:00"), watching = false)

        assertEquals(0, result.addedMillis)
        assertEquals(0, result.discardedMillis)
        assertEquals(at("2026-08-23T03:00:00"), result.state.lastSampleAtMs)
    }

    @Test
    fun `a gap across the reset is clamped on the part that belongs to today`() {
        val anchored = fresh("2026-08-22").copy(lastSampleAtMs = at("2026-08-22T20:00:00"))

        val result = counter.sample(anchored, at("2026-08-23T06:00:00"), watching = true)

        assertEquals(day("2026-08-23"), result.state.day)
        assertEquals(0, result.addedMillis)
        // Two hours since 04:00, all of it unaccounted for. The eight hours before the reset
        // are not reported: they belong to a day whose total is closed, not to a gap.
        assertEquals(2 * 3_600_000L, result.discardedMillis)
    }

    @Test
    fun `time before the reset is dropped without being called a gap`() {
        val anchored = fresh("2026-08-22").copy(lastSampleAtMs = at("2026-08-23T03:59:50"))

        val result = counter.sample(anchored, at("2026-08-23T04:00:00"), watching = true)

        assertEquals(day("2026-08-23"), result.state.day)
        assertEquals(0, result.addedMillis)
        assertEquals(0, result.discardedMillis)
    }

    @Test
    fun `the clock moving backwards adds nothing and re-anchors`() {
        val anchored = fresh("2026-08-22").copy(
            usedMillis = 30_000,
            lastSampleAtMs = at("2026-08-22T20:00:10"),
        )

        val result = counter.sample(anchored, at("2026-08-22T20:00:05"), watching = true)

        assertEquals(0, result.addedMillis)
        assertEquals(30_000, result.state.usedMillis)
        assertEquals(at("2026-08-22T20:00:05"), result.state.lastSampleAtMs)
    }

    @Test
    fun `an interval spanning the reset gives the new day only its own part`() {
        val anchored = fresh("2026-08-22").copy(
            usedMillis = 3_600_000,
            lastSampleAtMs = at("2026-08-23T03:59:55"),
        )

        val result = counter.sample(anchored, at("2026-08-23T04:00:05"), watching = true)

        assertEquals(day("2026-08-23"), result.state.day)
        // Five seconds of it fell after 04:00; the other five belong to a day already closed.
        assertEquals(5_000, result.addedMillis)
        assertEquals(5_000, result.state.usedMillis)
        assertEquals(0, result.state.bonusMillis)
        assertTrue(result.state.perAppMillis.isEmpty())
    }

    @Test
    fun `a gap of several days counts only from this morning, and is still clamped`() {
        val counter = ScreenTimeCounter(clock, maxIntervalMillis = Long.MAX_VALUE)
        val anchored = fresh("2026-08-18").copy(
            usedMillis = 7_200_000,
            lastSampleAtMs = at("2026-08-18T21:00:00"),
        )

        val result = counter.sample(anchored, at("2026-08-22T20:00:00"), watching = true)

        assertEquals(day("2026-08-22"), result.state.day)
        // From 04:00 today, not from four days ago.
        assertEquals(16 * 3_600_000L, result.addedMillis)
    }

    @Test
    fun `repeated fractional intervals do not drift`() {
        // Ten and a half seconds, sixty times. Rounding each sample down to whole seconds
        // would lose thirty of the six hundred and thirty, which is the undercount that
        // milliseconds in the state exist to prevent.
        var state = fresh("2026-08-22").copy(lastSampleAtMs = at("2026-08-22T20:00:00"))
        var now = at("2026-08-22T20:00:00")

        repeat(60) {
            now += 10_500
            state = counter.sample(state, now, watching = true).state
        }

        assertEquals(630, state.usedSeconds)
    }

    @Test
    fun `time is attributed to the app that was watched`() {
        var state = fresh("2026-08-22").copy(lastSampleAtMs = at("2026-08-22T20:00:00"))

        state = counter.sample(state, at("2026-08-22T20:00:10"), true, "com.netflix.ninja").state
        state = counter.sample(state, at("2026-08-22T20:00:20"), true, "com.netflix.ninja").state
        state = counter.sample(state, at("2026-08-22T20:00:25"), true, "pl.tvn.player.tv").state

        assertEquals(mapOf("com.netflix.ninja" to 20L, "pl.tvn.player.tv" to 5L), state.perAppSeconds)
        assertEquals(25, state.usedSeconds)
    }

    @Test
    fun `a restart mid-session neither loses nor doubles the time`() {
        var state = fresh("2026-08-22").copy(lastSampleAtMs = at("2026-08-22T20:00:00"))
        state = counter.sample(state, at("2026-08-22T20:00:10"), watching = true).state

        // Persisted, process killed, brought back, and sampled again from the same anchor.
        val restored = BudgetState(
            day = state.day,
            usedMillis = state.usedMillis,
            lastSampleAtMs = state.lastSampleAtMs,
        )
        val result = counter.sample(restored, at("2026-08-22T20:00:20"), watching = true)

        assertEquals(20, result.state.usedSeconds)
    }

    @Test
    fun `no limit means no answer about what is left, not zero`() {
        assertNull(counter.remainingSeconds(fresh("2026-08-22"), limitSeconds = null))
        assertFalse(counter.isSpent(fresh("2026-08-22"), limitSeconds = null))
    }

    @Test
    fun `what is left counts the limit plus any bonus, and floors at zero`() {
        val state = fresh("2026-08-22").copy(usedMillis = 3_600_000, bonusMillis = 900_000)

        assertEquals(900, counter.remainingSeconds(state, limitSeconds = 3_600))
        assertEquals(0, counter.remainingSeconds(state, limitSeconds = 600))
        assertTrue(counter.isSpent(state, limitSeconds = 600))
        assertFalse(counter.isSpent(state, limitSeconds = 3_600))
    }
}
