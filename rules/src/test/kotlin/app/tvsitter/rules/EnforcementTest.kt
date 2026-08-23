/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.rules

import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertNull
import org.junit.jupiter.api.Test
import java.time.LocalDate
import java.time.ZoneId

class EnforcementTest {

    private val counter = ScreenTimeCounter(BudgetClock(ZoneId.of("Europe/Warsaw")))
    private val today = BudgetState(day = LocalDate.parse("2026-08-22"))

    @Test
    fun `no limit calls for nothing, which is not the same as plenty of time`() {
        assertEquals(BudgetVerdict.WITHIN, BudgetEnforcement.verdictFor(null))
    }

    @Test
    fun `the boundaries are where they are documented`() {
        assertEquals(BudgetVerdict.WITHIN, BudgetEnforcement.verdictFor(301))
        assertEquals(BudgetVerdict.WARN, BudgetEnforcement.verdictFor(300))
        assertEquals(BudgetVerdict.WARN, BudgetEnforcement.verdictFor(1))
        assertEquals(BudgetVerdict.SPENT, BudgetEnforcement.verdictFor(0))
    }

    @Test
    fun `a negative remainder is spent rather than a surprise`() {
        // remainingSeconds floors at zero, but a caller computing its own arithmetic should
        // not be able to talk this into WITHIN.
        assertEquals(BudgetVerdict.SPENT, BudgetEnforcement.verdictFor(-60))
    }

    @Test
    fun `the warning window is configurable without touching the boundaries`() {
        assertEquals(BudgetVerdict.WITHIN, BudgetEnforcement.verdictFor(120, warningSeconds = 60))
        assertEquals(BudgetVerdict.WARN, BudgetEnforcement.verdictFor(60, warningSeconds = 60))
    }

    @Test
    fun `a suspended limit is no limit, not a limit that is being ignored`() {
        val spent = today.copy(usedMillis = 3_600_000)

        assertEquals(0, counter.remainingSeconds(spent, limitSeconds = 600))
        assertNull(counter.remainingSeconds(spent.copy(limitSuspended = true), 600))
        assertNull(counter.effectiveLimitSeconds(spent.copy(limitSuspended = true), 600))
        assertEquals(600, counter.effectiveLimitSeconds(spent, 600))
    }

    @Test
    fun `suspending tonight does not survive the reset`() {
        val suspended = today.copy(
            limitSuspended = true,
            usedMillis = 3_600_000,
            lastSampleAtMs = 1_787_000_000_000,
        )
        val clock = BudgetClock(ZoneId.of("Europe/Warsaw"))
        val counter = ScreenTimeCounter(clock, maxIntervalMillis = Long.MAX_VALUE)

        // Two days later: the rollover builds a fresh day, and "not tonight" was about a night
        // that is over.
        val next = counter.sample(suspended, 1_787_000_000_000 + 2 * 86_400_000, watching = false)

        assertEquals(false, next.state.limitSuspended)
    }

    @Test
    fun `a bonus buys time against the same limit`() {
        val state = today.copy(usedMillis = 3_600_000, bonusMillis = 900_000)

        assertEquals(900, counter.remainingSeconds(state, limitSeconds = 3_600))
        assertEquals(BudgetVerdict.WITHIN, BudgetEnforcement.verdictFor(900))
    }

    @Test
    fun `the nearest threshold passed is the one in force`() {
        val ladder = listOf(900L, 300L)

        assertNull(BudgetEnforcement.warningAt(901, ladder), "nothing has been passed yet")
        assertEquals(900, BudgetEnforcement.warningAt(900, ladder))
        assertEquals(900, BudgetEnforcement.warningAt(400, ladder), "still the quarter-hour one")
        assertEquals(300, BudgetEnforcement.warningAt(300, ladder))
        assertEquals(300, BudgetEnforcement.warningAt(1, ladder))
    }

    @Test
    fun `past the end is not a warning, it is the end`() {
        assertNull(BudgetEnforcement.warningAt(0, listOf(300L)))
        assertNull(BudgetEnforcement.warningAt(-30, listOf(300L)))
    }

    @Test
    fun `no thresholds is no warning at any point`() {
        assertNull(BudgetEnforcement.warningAt(60, emptyList()))
        assertEquals(BudgetVerdict.WITHIN, BudgetEnforcement.verdictFor(60, emptyList()))
        assertEquals(BudgetVerdict.SPENT, BudgetEnforcement.verdictFor(0, emptyList()), "the end still ends")
    }

    @Test
    fun `no limit is no warning either`() {
        assertNull(BudgetEnforcement.warningAt(null, listOf(300L)))
        assertEquals(BudgetVerdict.WITHIN, BudgetEnforcement.verdictFor(null, listOf(300L)))
    }
}
