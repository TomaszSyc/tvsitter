/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.rules

import java.time.Instant
import java.time.LocalDate

/**
 * How much of one budget day has been spent.
 *
 * Milliseconds rather than seconds on purpose. Sampling every ten seconds and rounding each
 * sample down to whole seconds discards up to a second every time, which is a systematic
 * undercount of a few percent — small enough not to notice and large enough to make a parent
 * wrong about what happened.
 */
data class BudgetState(
    val day: LocalDate,
    val usedMillis: Long = 0,
    val bonusMillis: Long = 0,
    val perAppMillis: Map<String, Long> = emptyMap(),
    /**
     * When the last sample was taken, as wall-clock milliseconds, or null if none has been.
     *
     * This is the anchor the next interval is measured from, which is why it is persisted
     * alongside the totals: without it, a restart cannot tell a long absence from a long
     * session.
     */
    val lastSampleAtMs: Long? = null,
) {
    val usedSeconds: Long get() = usedMillis / MILLIS_PER_SECOND
    val bonusSeconds: Long get() = bonusMillis / MILLIS_PER_SECOND
    val perAppSeconds: Map<String, Long>
        get() = perAppMillis.mapValues { (_, millis) -> millis / MILLIS_PER_SECOND }

    private companion object {
        const val MILLIS_PER_SECOND = 1000L
    }
}

/**
 * What one sample did.
 *
 * [discardedMillis] is not noise to be swallowed: it is the length of an interval the counter
 * refused to guess about, and the only place a caller can notice that the device was away
 * longer than sampling can account for. That is what reconciliation against
 * `UsageStatsManager` is for, and it cannot be asked for if nobody says it happened.
 */
data class SampleResult(val state: BudgetState, val addedMillis: Long = 0, val discardedMillis: Long = 0)

/**
 * Counts screen time against the budget day.
 *
 * Time is accumulated from wall-clock differences between samples, not by counting ticks. A
 * tick counter loses whatever the last interval held when the process dies, and drifts
 * whenever the timer is late — which on Android it will be. Measuring the interval instead
 * makes the accounting independent of how regularly anybody remembers to call [sample].
 *
 * Plain Kotlin with no Android dependencies, so it tests on the JVM.
 */
class ScreenTimeCounter(
    private val clock: BudgetClock,
    /**
     * The longest interval a single sample will believe.
     *
     * The wall clock is needed for the calendar and cannot be trusted for durations: an NTP
     * correction moves it, and a device that suspends stops sampling without saying so. If the
     * screen was last known to be on and the next sample arrives eight hours later, adding
     * eight hours would be inventing an evening nobody watched.
     */
    private val maxIntervalMillis: Long = DEFAULT_MAX_INTERVAL_MILLIS,
) {

    /**
     * Account for the interval between the previous sample and [nowMs].
     *
     * [watching] describes the interval, not the instant, which is why the caller has to
     * sample at every transition rather than only on a timer: an interval that was half
     * watched can only be counted correctly if it is cut where the state changed.
     */
    fun sample(state: BudgetState, nowMs: Long, watching: Boolean, appId: String? = null): SampleResult {
        val today = clock.budgetDay(Instant.ofEpochMilli(nowMs))
        val previous = state.lastSampleAtMs
            ?: // Nothing to measure from yet; this sample only plants the anchor.
            return SampleResult(state.copy(day = today, lastSampleAtMs = nowMs))

        val rolledOver = today != state.day
        val base = if (rolledOver) BudgetState(day = today) else state

        // After a rollover only the part of the interval inside the new day counts. The rest
        // belonged to a day whose total is closed and already published.
        val startMs = if (rolledOver) {
            maxOf(previous, clock.dayStart(Instant.ofEpochMilli(nowMs)).toEpochMilli())
        } else {
            previous
        }

        val elapsed = nowMs - startMs
        val anchored = base.copy(lastSampleAtMs = nowMs)

        // Not an error worth refusing: a clock correction can move time backwards, and the
        // right response is to re-anchor and carry on rather than to count a negative session.
        if (elapsed <= 0) return SampleResult(anchored)

        if (elapsed > maxIntervalMillis) {
            return SampleResult(anchored, discardedMillis = elapsed)
        }

        if (!watching) return SampleResult(anchored)

        return SampleResult(
            anchored.copy(
                usedMillis = base.usedMillis + elapsed,
                perAppMillis = base.perAppMillis.plusMillis(appId, elapsed),
            ),
            addedMillis = elapsed,
        )
    }

    /**
     * What is left of the day, or null when no limit applies.
     *
     * Null rather than zero, all the way through to the dashboard. "No limit tonight" and
     * "time is up" are different answers, and collapsing them turns an unlimited evening into
     * an instant lock.
     */
    fun remainingSeconds(state: BudgetState, limitSeconds: Long?): Long? {
        if (limitSeconds == null) return null
        return maxOf(0, limitSeconds + state.bonusSeconds - state.usedSeconds)
    }

    /** Whether the day's allowance is spent. False whenever there is no limit at all. */
    fun isSpent(state: BudgetState, limitSeconds: Long?): Boolean = remainingSeconds(state, limitSeconds) == 0L

    private fun Map<String, Long>.plusMillis(appId: String?, millis: Long): Map<String, Long> {
        if (appId == null) return this
        return this + (appId to (getOrElse(appId) { 0 } + millis))
    }

    companion object {
        /**
         * Three times a ten-second sample, which tolerates a late timer without believing a
         * suspend. Anything longer is a gap to be reconciled, not an interval to be counted.
         */
        const val DEFAULT_MAX_INTERVAL_MILLIS: Long = 30_000
    }
}
