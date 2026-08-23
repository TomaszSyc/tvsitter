/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.rules

import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertNotEquals
import org.junit.jupiter.api.Assertions.assertNull
import org.junit.jupiter.api.Test
import java.time.DayOfWeek
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.LocalTime
import java.time.ZoneId

class RuleEngineTest {

    private val warsaw = ZoneId.of("Europe/Warsaw")
    private val engine = RuleEngine(BudgetClock(warsaw))

    private fun at(text: String): Long = LocalDateTime.parse(text).atZone(warsaw).toInstant().toEpochMilli()

    /** 2026-08-24 is a Monday, 2026-08-22 a Saturday. */
    private fun onDay(text: String) = BudgetState(day = LocalDate.parse(text))

    private val school = Window("school", LocalTime.of(16, 0), LocalTime.of(19, 30), setOf(DayOfWeek.MONDAY))

    @Test
    fun `no rules is nothing to do`() {
        val judgement = engine.judge(Rules.NONE, onDay("2026-08-24"), null, at("2026-08-24T17:00:00"))

        assertEquals(Judgement.NOTHING, judgement)
    }

    @Test
    fun `the day's own limit is the one enforced`() {
        val rules = Rules(dailyLimitSeconds = 3600, dayLimitSeconds = mapOf(DayOfWeek.SATURDAY to 7200))
        val used = onDay("2026-08-22").copy(usedMillis = 3_600_000)

        val saturday = engine.judge(rules, used, null, at("2026-08-22T17:00:00"))
        val monday = engine.judge(
            rules,
            used.copy(day = LocalDate.parse("2026-08-24")),
            null,
            at("2026-08-24T17:00:00"),
        )

        assertEquals(3600, saturday.remainingSeconds, "Saturday allows two hours")
        assertEquals(0, monday.remainingSeconds, "Monday allows one, and it is gone")
        assertEquals(LockReason.DAILY_LIMIT, monday.reason)
    }

    @Test
    fun `an open window is the window in force`() {
        val rules = Rules(windows = listOf(school))

        val judgement = engine.judge(rules, onDay("2026-08-24"), null, at("2026-08-24T17:00:00"))

        assertEquals(BudgetVerdict.WITHIN, judgement.state)
        assertEquals("school", judgement.decision.windowId, "this is what active_window publishes")
        assertEquals(150 * 60L, judgement.remainingSeconds, "two and a half hours until it closes")
    }

    @Test
    fun `outside every window the hours are the reason, not the budget`() {
        // Which matters beyond the wording: asking a parent for more time cannot answer this one.
        val rules = Rules(dailyLimitSeconds = 7200, windows = listOf(school))

        val judgement = engine.judge(rules, onDay("2026-08-24"), null, at("2026-08-24T20:00:00"))

        assertEquals(BudgetVerdict.SPENT, judgement.state)
        assertEquals(LockReason.OUTSIDE_WINDOW, judgement.reason)
        assertEquals(0, judgement.remainingSeconds)
    }

    @Test
    fun `before the window opens it says when`() {
        val rules = Rules(windows = listOf(school))

        val judgement = engine.judge(rules, onDay("2026-08-24"), null, at("2026-08-24T14:00:00"))

        assertEquals(LockReason.OUTSIDE_WINDOW, judgement.reason)
        assertEquals(LocalTime.of(16, 0), judgement.opensAt, "allowed again at four is worth saying")
    }

    @Test
    fun `with nothing left today it says nothing rather than tomorrow`() {
        val rules = Rules(windows = listOf(school))

        val judgement = engine.judge(rules, onDay("2026-08-24"), null, at("2026-08-24T21:00:00"))

        assertNull(judgement.opensAt)
    }

    @Test
    fun `a day with no window of its own is closed, not unrestricted`() {
        // The direction this cuts: a window list is a list of permissions, so a day nobody wrote
        // a window for is a day with no permission. The other reading fails by silently not
        // applying, which is the worse failure for a parental control (D27).
        val rules = Rules(windows = listOf(school))

        val judgement = engine.judge(rules, onDay("2026-08-22"), null, at("2026-08-22T17:00:00"))

        assertEquals(BudgetVerdict.SPENT, judgement.state)
        assertEquals(LockReason.OUTSIDE_WINDOW, judgement.reason)
    }

    @Test
    fun `a window ending after midnight is still open at half past twelve`() {
        // 00:30 on Tuesday is still Monday's budget day, so a Monday window has to still count.
        val film = Window("film", LocalTime.of(20, 0), LocalTime.of(1, 0), setOf(DayOfWeek.MONDAY))

        val judgement = engine.judge(
            Rules(windows = listOf(film)),
            onDay("2026-08-24"),
            null,
            at("2026-08-25T00:30:00"),
        )

        assertEquals(BudgetVerdict.WITHIN, judgement.state)
        assertEquals(30 * 60L, judgement.remainingSeconds, "half an hour before it closes")
    }

    @Test
    fun `the same window is shut at half past one`() {
        val film = Window("film", LocalTime.of(20, 0), LocalTime.of(1, 0), setOf(DayOfWeek.MONDAY))

        val judgement = engine.judge(
            Rules(windows = listOf(film)),
            onDay("2026-08-24"),
            null,
            at("2026-08-25T01:30:00"),
        )

        assertEquals(BudgetVerdict.SPENT, judgement.state)
    }

    @Test
    fun `whichever runs out first is the one counting down`() {
        val rules = Rules(dailyLimitSeconds = 7200, windows = listOf(school))
        // Ten minutes before the window closes, with an hour of budget still unspent.
        val judgement = engine.judge(rules, onDay("2026-08-24"), null, at("2026-08-24T19:20:00"))

        assertEquals(600, judgement.remainingSeconds, "the window, not the budget")
    }

    @Test
    fun `a closing window warns exactly as a spent budget does`() {
        val rules = Rules(dailyLimitSeconds = 7200, windows = listOf(school))

        val judgement = engine.judge(rules, onDay("2026-08-24"), null, at("2026-08-24T19:25:00"))

        assertEquals(BudgetVerdict.WARN, judgement.state)
        assertEquals(300, judgement.decision.warnAtSeconds)
        assertEquals(LockReason.OUTSIDE_WINDOW, judgement.reason)
    }

    @Test
    fun `two thresholds are two warnings, and one is not the other`() {
        // The whole point of a list. Both are WARN, so a caller comparing verdicts would show one
        // warning all evening; comparing decisions shows two.
        val rules = Rules(dailyLimitSeconds = 3600, warnBeforeSeconds = listOf(900, 300))
        val state = onDay("2026-08-24")

        val quarter = engine.judge(rules, state.copy(usedMillis = 2_760_000), null, at("2026-08-24T17:00:00"))
        val five = engine.judge(rules, state.copy(usedMillis = 3_360_000), null, at("2026-08-24T17:00:00"))

        assertEquals(900, quarter.decision.warnAtSeconds)
        assertEquals(300, five.decision.warnAtSeconds)
        assertNotEquals(quarter.decision, five.decision, "a caller must be able to tell them apart")
    }

    @Test
    fun `no thresholds is no warning, right up to the lock`() {
        val rules = Rules(dailyLimitSeconds = 3600, warnBeforeSeconds = emptyList())
        val state = onDay("2026-08-24").copy(usedMillis = 3_599_000)

        val judgement = engine.judge(rules, state, null, at("2026-08-24T17:00:00"))

        assertEquals(BudgetVerdict.WITHIN, judgement.state)
        assertNull(judgement.decision.warnAtSeconds)
    }

    @Test
    fun `a spent app budget displaces the app and leaves the screen alone`() {
        val rules = Rules(dailyLimitSeconds = 7200, appLimitSeconds = mapOf(NETFLIX to 1800))
        val state = onDay("2026-08-24").copy(perAppMillis = mapOf(NETFLIX to 1_800_000))

        val judgement = engine.judge(rules, state, NETFLIX, at("2026-08-24T17:00:00"))

        assertEquals(BudgetVerdict.WITHIN, judgement.state, "the day still has time in it")
        assertEquals(NETFLIX, judgement.decision.displaceApp)
        assertEquals(LockReason.APP_LIMIT, judgement.reason)
    }

    @Test
    fun `a blocked app is a budget of zero`() {
        val rules = Rules(appLimitSeconds = mapOf(NETFLIX to 0))

        val judgement = engine.judge(rules, onDay("2026-08-24"), NETFLIX, at("2026-08-24T17:00:00"))

        assertEquals(NETFLIX, judgement.decision.displaceApp)
    }

    @Test
    fun `one app's budget says nothing about another app`() {
        val rules = Rules(appLimitSeconds = mapOf(NETFLIX to 0))

        val judgement = engine.judge(rules, onDay("2026-08-24"), YOUTUBE, at("2026-08-24T17:00:00"))

        assertEquals(Judgement.NOTHING, judgement)
    }

    @Test
    fun `a spent day covers the screen even when an app ran out as well`() {
        val rules = Rules(dailyLimitSeconds = 3600, appLimitSeconds = mapOf(NETFLIX to 1800))
        val state = onDay("2026-08-24").copy(usedMillis = 3_600_000, perAppMillis = mapOf(NETFLIX to 1_800_000))

        val judgement = engine.judge(rules, state, NETFLIX, at("2026-08-24T17:00:00"))

        assertEquals(BudgetVerdict.SPENT, judgement.state)
        assertEquals(LockReason.DAILY_LIMIT, judgement.reason, "the bigger rule is the one to explain")
        assertNull(judgement.decision.displaceApp, "nothing to displace behind a covered screen")
    }

    @Test
    fun `a limit set aside for tonight sets the hours aside with it`() {
        // Otherwise lifting the lock at nine uncovers the screen and the next sample covers it
        // again, which is the failure that reads as a broken television.
        val rules = Rules(dailyLimitSeconds = 3600, windows = listOf(school))
        val state = onDay("2026-08-24").copy(usedMillis = 3_600_000, limitSuspended = true)

        val judgement = engine.judge(rules, state, null, at("2026-08-24T21:00:00"))

        assertEquals(BudgetVerdict.WITHIN, judgement.state)
        assertNull(judgement.remainingSeconds)
    }

    @Test
    fun `an app budget survives a limit set aside for the evening`() {
        // The suspension answers the lock the day's budget put up. An app's own allowance is a
        // different rule and nobody lifted it.
        val rules = Rules(dailyLimitSeconds = 3600, appLimitSeconds = mapOf(NETFLIX to 1800))
        val state = onDay("2026-08-24")
            .copy(usedMillis = 3_600_000, perAppMillis = mapOf(NETFLIX to 1_800_000), limitSuspended = true)

        val judgement = engine.judge(rules, state, NETFLIX, at("2026-08-24T21:00:00"))

        assertEquals(NETFLIX, judgement.decision.displaceApp)
    }

    @Test
    fun `bonus time counts against the day, not against an app`() {
        val rules = Rules(dailyLimitSeconds = 3600, appLimitSeconds = mapOf(NETFLIX to 1800))
        val state = onDay("2026-08-24")
            .copy(usedMillis = 3_600_000, bonusMillis = 900_000, perAppMillis = mapOf(NETFLIX to 1_800_000))

        val judgement = engine.judge(rules, state, NETFLIX, at("2026-08-24T17:00:00"))

        assertEquals(NETFLIX, judgement.decision.displaceApp, "granted minutes did not renew Netflix")
        assertEquals(0, judgement.remainingSeconds, "the app is what runs out first")
    }

    private companion object {
        const val NETFLIX = "com.netflix.ninja"
        const val YOUTUBE = "com.google.android.youtube.tv"
    }
}
