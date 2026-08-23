/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.rules

import java.time.Instant
import java.time.LocalDate
import java.time.LocalTime
import java.time.ZoneId
import java.time.ZonedDateTime

/**
 * Clock for the budget day.
 *
 * The accounting day starts at [dayStartHour], not at midnight. Without that, a child
 * watching at 23:59 gets a fresh allowance at 00:00 for the rest of the night — the exact
 * opposite of what this app is for.
 *
 * The whole class is plain Kotlin with no Android dependencies so it can be tested on the
 * JVM without an emulator.
 */
class BudgetClock(
    /** Public because a window is wall-clock, and reading it needs the same zone as the day. */
    val zone: ZoneId,
    val dayStartHour: Int = DEFAULT_DAY_START_HOUR,
) {
    init {
        require(dayStartHour in HOURS_OF_DAY) { "dayStartHour must be within $HOURS_OF_DAY, was $dayStartHour" }
    }

    /** The budget day that [instant] belongs to. */
    fun budgetDay(instant: Instant): LocalDate {
        val local = instant.atZone(zone)
        return if (local.hour < dayStartHour) {
            local.toLocalDate().minusDays(1)
        } else {
            local.toLocalDate()
        }
    }

    /** Whether both moments fall in the same budget day, and therefore share one allowance. */
    fun isSameBudgetDay(first: Instant, second: Instant): Boolean = budgetDay(first) == budgetDay(second)

    /**
     * The moment the budget day containing [instant] began, at or before it.
     *
     * Needed to attribute an interval that spans a reset: the part after the boundary belongs
     * to the new day, and the part before it to a day whose total is already closed. Correct
     * for any number of elapsed days, which matters after a TV has been off for a week.
     */
    fun dayStart(instant: Instant): Instant = ZonedDateTime.of(
        budgetDay(instant),
        LocalTime.of(dayStartHour, 0),
        zone,
    ).toInstant()

    /**
     * The next moment the counter resets, always strictly after [instant].
     *
     * [ZonedDateTime.of] is used on purpose: across a daylight saving transition it resolves
     * a non-existent local time by shifting forward instead of throwing.
     */
    fun nextReset(instant: Instant): Instant = ZonedDateTime.of(
        budgetDay(instant).plusDays(1),
        LocalTime.of(dayStartHour, 0),
        zone,
    ).toInstant()

    companion object {
        /** 04:00 — "small hours" in human terms, and safely outside real viewing time. */
        const val DEFAULT_DAY_START_HOUR: Int = 4

        private val HOURS_OF_DAY = 0..23
    }
}
