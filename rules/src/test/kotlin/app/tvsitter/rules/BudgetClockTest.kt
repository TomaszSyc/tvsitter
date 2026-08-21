/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.rules

import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertFalse
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.assertThrows
import java.time.Instant
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.ZoneId

class BudgetClockTest {

    private val warsaw = ZoneId.of("Europe/Warsaw")
    private val clock = BudgetClock(warsaw, dayStartHour = 4)

    private fun at(text: String): Instant = LocalDateTime.parse(text).atZone(warsaw).toInstant()

    @Test
    fun `watching past midnight stays within the same budget day`() {
        val before = at("2026-08-21T23:59:00")
        val after = at("2026-08-22T00:30:00")

        assertTrue(clock.isSameBudgetDay(before, after))
        assertEquals(LocalDate.parse("2026-08-21"), clock.budgetDay(after))
    }

    @Test
    fun `the day boundary falls exactly at the configured hour`() {
        assertEquals(LocalDate.parse("2026-08-21"), clock.budgetDay(at("2026-08-22T03:59:59")))
        assertEquals(LocalDate.parse("2026-08-22"), clock.budgetDay(at("2026-08-22T04:00:00")))
    }

    @Test
    fun `two consecutive evenings are different budget days`() {
        assertFalse(clock.isSameBudgetDay(at("2026-08-21T20:00:00"), at("2026-08-22T20:00:00")))
    }

    @Test
    fun `the next reset is always in the future`() {
        listOf(
            "2026-08-21T04:00:00",
            "2026-08-21T20:00:00",
            "2026-08-21T23:59:59",
            "2026-08-22T00:00:01",
            "2026-08-22T03:59:59",
        ).forEach { moment ->
            val now = at(moment)
            assertTrue(clock.nextReset(now).isAfter(now), "reset does not follow $moment")
        }
    }

    @Test
    fun `a late night session resets the same morning`() {
        assertEquals(at("2026-08-22T04:00:00"), clock.nextReset(at("2026-08-22T01:00:00")))
        assertEquals(at("2026-08-22T04:00:00"), clock.nextReset(at("2026-08-21T21:00:00")))
    }

    @Test
    fun `the spring daylight saving switch does not break the day boundary`() {
        // In Poland the clock jumps from 02:00 to 03:00 on 2026-03-29, so 04:00 exists but
        // the day is only 23 hours long — this has to work without throwing.
        val duringShortDay = at("2026-03-29T05:00:00")
        assertEquals(LocalDate.parse("2026-03-29"), clock.budgetDay(duringShortDay))
        assertEquals(at("2026-03-30T04:00:00"), clock.nextReset(duringShortDay))
    }

    @Test
    fun `midnight as the start of the day also works`() {
        val midnightClock = BudgetClock(warsaw, dayStartHour = 0)
        assertEquals(LocalDate.parse("2026-08-22"), midnightClock.budgetDay(at("2026-08-22T00:00:01")))
        assertEquals(at("2026-08-23T00:00:00"), midnightClock.nextReset(at("2026-08-22T00:00:01")))
    }

    @Test
    fun `a nonsensical day start hour is rejected`() {
        assertThrows<IllegalArgumentException> { BudgetClock(warsaw, dayStartHour = 24) }
        assertThrows<IllegalArgumentException> { BudgetClock(warsaw, dayStartHour = -1) }
    }
}
