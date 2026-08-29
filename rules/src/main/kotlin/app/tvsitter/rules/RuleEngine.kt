/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.rules

import java.time.DayOfWeek
import java.time.Instant
import java.time.LocalTime

/** What is stopping the viewing, when something is. */
enum class LockReason(val wire: String) {
    NONE("none"),

    /** The hours do not allow it. Asking for more time cannot answer this one. */
    OUTSIDE_WINDOW("outside_window"),

    /** The day's allowance is gone. */
    DAILY_LIMIT("daily_limit"),

    /** This app's own allowance is gone. The rest of the television is unaffected. */
    APP_LIMIT("app_limit"),
    ;

    companion object {
        /** A parent's decision, which is not one of the rules and never comes from the engine. */
        const val MANUAL: String = "manual"
    }
}

/**
 * What the screen should do, with no mention of how long is left.
 *
 * Separated from the countdown on purpose. Sampling runs every ten seconds, so a judgement that
 * carried the remaining seconds would differ every time and a caller comparing judgements to
 * avoid nagging would nag anyway. This is the part that is allowed to repeat and must not.
 */
data class Decision(
    val state: BudgetVerdict,
    val reason: LockReason = LockReason.NONE,
    /** Which warning threshold is in force, so that two in an evening are two (#39). */
    val warnAtSeconds: Long? = null,
    /** The window in force, which is what `active_window` publishes. */
    val windowId: String? = null,
    /** A package to send to the background. Set only when the screen is *not* being covered. */
    val displaceApp: String? = null,
)

/**
 * The whole answer: what to do, how long is left, and when viewing is allowed again.
 *
 * [remainingSeconds] belongs to whichever rule runs out first, so one countdown drives the
 * warnings, the banner and the lock no matter which rule is the reason.
 */
data class Judgement(
    val decision: Decision,
    val remainingSeconds: Long? = null,
    /** For a window that has not opened yet, the time it does. Null when nothing more today. */
    val opensAt: LocalTime? = null,
) {
    val state: BudgetVerdict get() = decision.state
    val reason: LockReason get() = decision.reason

    companion object {
        val NOTHING: Judgement = Judgement(Decision(BudgetVerdict.WITHIN))
    }
}

/**
 * Turns the rules, the clock and what has been watched into one answer.
 *
 * Every rule ends up as the same shape — a number of seconds before viewing has to stop — which
 * is what keeps the schedule from needing its own warning ladder, its own countdown and its own
 * lock. The smallest of them wins, and the reason says which one it was.
 *
 * Pure, so all of it is tested on the JVM. What is not here: doing anything about the answer.
 */
class RuleEngine(private val clock: BudgetClock) {

    private data class Constraint(val reason: LockReason, val remainingSeconds: Long)

    fun judge(rules: Rules, state: BudgetState, appId: String?, nowMs: Long): Judgement {
        val moment = Instant.ofEpochMilli(nowMs)
        val day = clock.budgetDay(moment).dayOfWeek
        val second = secondOfBudgetDay(moment.atZone(clock.zone).toLocalTime())

        // A limit set aside for tonight sets the hours aside with it. A parent who lifts the
        // lock at nine has answered the evening, and re-covering the screen ten seconds later
        // because the window closed is the failure that reads as a broken television.
        val hoursApply = rules.windows.isNotEmpty() && !state.limitSuspended
        val window = if (hoursApply) windowAt(rules, day, second) else null
        if (hoursApply && window == null) return closed(rules, day, second)

        val constraints = listOfNotNull(
            window?.let { Constraint(LockReason.OUTSIDE_WINDOW, secondsUntilClose(it, second)) },
            state.remainingSeconds(rules.limitFor(day))?.let { Constraint(LockReason.DAILY_LIMIT, it) },
            appConstraint(rules, state, appId),
        )

        val binding = constraints.minWithOrNull(
            compareBy({ it.remainingSeconds }, { it.reason.ordinal }),
        ) ?: return Judgement(Decision(BudgetVerdict.WITHIN, windowId = window?.id))

        return Judgement(
            decide(binding, rules, appId, window?.id),
            remainingSeconds = binding.remainingSeconds,
        )
    }

    private fun decide(binding: Constraint, rules: Rules, appId: String?, windowId: String?): Decision {
        val warnAt = BudgetEnforcement.warningAt(binding.remainingSeconds, rules.warnBeforeSeconds)
        val spent = binding.remainingSeconds <= 0

        // An app out of its own time does not cover the screen: the daily budget still has time
        // in it, and covering everything would punish the choice of app rather than the watching.
        if (spent && binding.reason == LockReason.APP_LIMIT) {
            return Decision(BudgetVerdict.WITHIN, binding.reason, windowId = windowId, displaceApp = appId)
        }

        val state = when {
            spent -> BudgetVerdict.SPENT
            warnAt != null -> BudgetVerdict.WARN
            else -> BudgetVerdict.WITHIN
        }
        val reason = if (state == BudgetVerdict.WITHIN) LockReason.NONE else binding.reason
        return Decision(state, reason, warnAtSeconds = warnAt, windowId = windowId)
    }

    private fun appConstraint(rules: Rules, state: BudgetState, appId: String?): Constraint? {
        val limit = appId?.let { rules.appLimitSeconds[it] } ?: return null
        return Constraint(LockReason.APP_LIMIT, maxOf(0, limit - state.usedSecondsBy(appId)))
    }

    /** Outside every window there is: the hours are the reason, and asking for time cannot help. */
    private fun closed(rules: Rules, day: DayOfWeek, second: Int): Judgement = Judgement(
        Decision(BudgetVerdict.SPENT, LockReason.OUTSIDE_WINDOW),
        remainingSeconds = 0,
        opensAt = nextOpening(rules, day, second),
    )

    private fun windowAt(rules: Rules, day: DayOfWeek, second: Int): Window? =
        rules.windows.firstOrNull { it.appliesOn(day) && covers(it, second) }

    private fun covers(window: Window, second: Int): Boolean {
        val from = secondOfBudgetDay(window.from)
        val to = secondOfBudgetDay(window.to)
        // A window may cross the day's own start — 02:00 to 06:00 straddles the 04:00 reset —
        // and then it is the outside of the interval that counts as being in it.
        return if (from <= to) second >= from && second < to else second >= from || second < to
    }

    private fun secondsUntilClose(window: Window, second: Int): Long {
        val to = secondOfBudgetDay(window.to)
        return if (to > second) (to - second).toLong() else (to + SECONDS_PER_DAY - second).toLong()
    }

    /**
     * The next window to open today, or null when there is nothing more.
     *
     * Today only. "Allowed again at four" is the sentence worth saying to a child standing in
     * front of a locked television; working out that the next one is on Saturday is a calendar
     * question, and one the lock screen has no room for anyway.
     */
    private fun nextOpening(rules: Rules, day: DayOfWeek, second: Int): LocalTime? = rules.windows
        .filter { it.appliesOn(day) }
        .filter { secondOfBudgetDay(it.from) > second }
        .minByOrNull { secondOfBudgetDay(it.from) }
        ?.from

    /**
     * Where a wall-clock time falls in the budget day, in seconds from its start.
     *
     * Everything is measured in this frame so that an evening window and the counter agree about
     * which day they are in: at 00:30 the counter is still charging yesterday's allowance, and a
     * window that ends at 01:00 has to still be open.
     */
    private fun secondOfBudgetDay(time: LocalTime): Int {
        val fromMidnight = time.toSecondOfDay()
        val dayStart = clock.dayStartHour * SECONDS_PER_HOUR
        return (fromMidnight - dayStart + SECONDS_PER_DAY) % SECONDS_PER_DAY
    }

    private companion object {
        const val SECONDS_PER_HOUR = 60 * 60
        const val SECONDS_PER_DAY = 24 * SECONDS_PER_HOUR
    }
}
