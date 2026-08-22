/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.tv

import android.content.Context
import android.util.Log
import app.tvsitter.rules.BudgetClock
import app.tvsitter.rules.BudgetState
import app.tvsitter.rules.ScreenTimeCounter
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import java.time.Instant
import java.time.ZoneId

/**
 * The counter, on the device.
 *
 * Owns the sampling interval, the persistence and the question of what counts as watching.
 * The arithmetic lives in [ScreenTimeCounter], which is plain Kotlin and tested on the JVM;
 * everything Android-shaped is here.
 */
class ScreenTimeTracker(
    private val context: Context,
    private val onDayRolled: () -> Unit = {},
    private val clock: BudgetClock = BudgetClock(ZoneId.systemDefault()),
) {
    private val counter = ScreenTimeCounter(clock)
    private val screenSavers = ScreenSaverPackages(context)
    private var scope: CoroutineScope? = null
    private var lastSavedAtMs = 0L

    /**
     * What was true *during* the interval now being closed, which is not what is true now.
     *
     * Both `ScreenState` and `ForegroundAppMonitor` announce a change after applying it, so at
     * the moment a callback runs the new value is already current. An interval that ended
     * because the screen went off was watched; one that ended because the app changed belongs
     * to the app that was showing. Reading "now" at sample time would charge every interval to
     * the state that replaced it, quietly moving time from Netflix to the launcher and losing
     * the last stretch before every screen-off.
     */
    private var screenOnDuringInterval = false
    private var appDuringInterval: String? = null

    @Volatile
    var state: BudgetState = BudgetState(day = clock.budgetDay(Instant.now()))
        private set

    val usedSeconds: Int get() = state.usedSeconds.toInt()
    val bonusSeconds: Int get() = state.bonusSeconds.toInt()
    val perAppSeconds: Map<String, Int> get() = state.perAppSeconds.mapValues { it.value.toInt() }

    /** Null when no limit applies, which is a different answer from zero. */
    fun remainingSeconds(limitSeconds: Long?): Int? = counter.remainingSeconds(state, limitSeconds)?.toInt()

    /**
     * Restores the counter and starts sampling.
     *
     * The restore happens inside the loop's coroutine rather than before it so that a slow
     * first read cannot delay the service starting; until it lands the counter reads zero,
     * which is honest — nothing is known yet.
     */
    fun start(scope: CoroutineScope, screenOn: () -> Boolean, appId: () -> String?) {
        this.scope = scope
        scope.launch {
            state = Settings(context).budget()
            Log.i(
                EnforcerService.TAG,
                "counter restored: day=${state.day} used=${state.usedSeconds}s " +
                    "anchor=${state.lastSampleAtMs}",
            )
            while (scope.isActive) {
                sample(screenOn(), appId())
                delay(SAMPLE_INTERVAL_MS)
            }
        }
    }

    /**
     * Closes the current interval at a transition.
     *
     * Called from the screen and foreground callbacks, so an interval is cut where the state
     * changed rather than at the next tick. Without it, up to a full interval of viewing is
     * charged to whatever came next, or lost.
     */
    fun sampleAtTransition(screenOn: Boolean, appId: String?) = sample(screenOn, appId)

    private fun sample(screenOnNow: Boolean, appIdNow: String?) {
        val watching = screenOnDuringInterval && !screenSavers.contains(appDuringInterval)
        val nowMs = System.currentTimeMillis()
        val previous = state

        val result = counter.sample(previous, nowMs, watching, appDuringInterval)
        state = result.state

        screenOnDuringInterval = screenOnNow
        appDuringInterval = appIdNow

        if (result.discardedMillis > 0) {
            // Not swallowed: this is the only sign that the device was away longer than
            // sampling can account for, and reconciliation cannot be asked for silently.
            Log.w(
                EnforcerService.TAG,
                "counter: ${result.discardedMillis / MILLIS_PER_SECOND}s unaccounted for",
            )
        }

        val rolled = previous.day != state.day
        if (rolled) {
            Log.i(EnforcerService.TAG, "counter: budget day is now ${state.day}")
            onDayRolled()
        }

        // Written when viewing stops, so the last slice is safe, and on a rollover. Not on
        // every idle sample: a screen saver left running overnight would otherwise rewrite
        // storage every ten seconds for eight hours, and there would be nothing new in it.
        // While nothing accrues there is nothing to lose — a stale anchor restored after a
        // kill is simply re-anchored by the first sample, which adds nothing.
        val stillWatching = screenOnNow && !screenSavers.contains(appIdNow)
        val stoppedWatching = watching && !stillWatching
        if (result.addedMillis > 0 || rolled || stoppedWatching) {
            persist(nowMs, force = rolled || stoppedWatching)
        }
    }

    private fun persist(nowMs: Long, force: Boolean) {
        if (!force && nowMs - lastSavedAtMs < SAVE_INTERVAL_MS) return
        lastSavedAtMs = nowMs
        val snapshot = state
        scope?.launch {
            runCatching { Settings(context).saveBudget(snapshot) }
                .onFailure { Log.w(EnforcerService.TAG, "counter: could not persist", it) }
        }
    }

    private companion object {
        /**
         * Ten seconds. Short enough that a lock lands within a sensible margin of the limit,
         * long enough not to write to storage constantly — and well inside the counter's own
         * clamp, so an ordinary late tick is never mistaken for a suspend.
         */
        const val SAMPLE_INTERVAL_MS = 10_000L

        /** A minute of viewing is the most a sudden death can cost. */
        const val SAVE_INTERVAL_MS = 60_000L

        const val MILLIS_PER_SECOND = 1000L
    }
}
