/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.tv

import android.content.Context
import android.media.AudioManager
import android.util.Log
import app.tvsitter.rules.Attention
import app.tvsitter.rules.AttentionRule
import app.tvsitter.rules.BudgetClock
import app.tvsitter.rules.BudgetState
import app.tvsitter.rules.Judgement
import app.tvsitter.rules.RuleEngine
import app.tvsitter.rules.Rules
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
    private val rules: () -> Rules = { Rules.NONE },
    private val onDayRolled: () -> Unit = {},
    private val onJudgement: (Judgement) -> Unit = {},
    private val clock: BudgetClock = BudgetClock(ZoneId.systemDefault()),
) {
    private val counter = ScreenTimeCounter(clock)
    private val engine = RuleEngine(clock)

    /**
     * The last answer the rules gave, kept so that the state payload and the lock agree.
     *
     * One judgement, read by both: publishing a second opinion worked out separately is how
     * Home Assistant ends up disagreeing with the television about why it is covered.
     */
    @Volatile
    var judgement: Judgement = Judgement.NOTHING
        private set
    private val screenSavers = ScreenSaverPackages(context)
    private val tvInputs = TvInputPackages(context)
    private val audioManager = context.getSystemService(AudioManager::class.java)
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
    private var playingDuringInterval = false

    /**
     * When something last happened: playback running, or the app in front changing.
     *
     * What makes the difference between browsing and an empty room. There is no signal for
     * "somebody pressed a button" on this television — it emits no user-interaction events at
     * all — so this is the closest thing to one.
     */
    private var lastActivityAtMs = System.currentTimeMillis()

    /** Logged when it changes rather than every ten seconds, which would say nothing. */
    private var wasWatching: Boolean? = null

    @Volatile
    var state: BudgetState = BudgetState(day = clock.budgetDay(Instant.now()))
        private set

    val usedSeconds: Int get() = state.usedSeconds.toInt()
    val bonusSeconds: Int get() = state.bonusSeconds.toInt()
    val perAppSeconds: Map<String, Int> get() = state.perAppSeconds.mapValues { it.value.toInt() }

    /**
     * Today's limit, null when none applies — which is a different answer from zero.
     *
     * Not always the plain daily one: a weekday and a Saturday can carry different numbers,
     * and the day that decides is the budget day — so watching at one in the morning is still
     * charged, and limited, by the evening it belongs to. Null while a limit is set aside for
     * tonight, because a limit set aside is no limit.
     */
    fun limitTodaySeconds(): Int? = counter.effectiveLimitSeconds(state, limitToday())?.toInt()

    /** What is left of it, ignoring windows and per-app budgets: that is what [judgement] is for. */
    fun remainingTodaySeconds(): Int? = counter.remainingSeconds(state, limitToday())?.toInt()

    private fun limitToday(): Long? = rules().limitFor(clock.budgetDay(Instant.now()).dayOfWeek)

    /**
     * Adds granted time to the day.
     *
     * A bonus rather than a reduction of what was used: the statistics still say what was
     * actually watched, which is the whole point of keeping them.
     */
    fun addBonus(seconds: Long) {
        state = state.copy(bonusMillis = state.bonusMillis + seconds * MILLIS_PER_SECOND)
        Log.i(EnforcerService.TAG, "counter: granted ${seconds}s, bonus now ${state.bonusSeconds}s")
        persistNow()
        announceVerdict()
    }

    /**
     * Sets the limit aside for the rest of this budget day.
     *
     * What `unlock` with no minutes means: not "some more time" but "not tonight". It clears
     * itself at the next reset, because it lives in the day's state.
     */
    fun suspendLimitUntilReset() {
        state = state.copy(limitSuspended = true)
        Log.i(EnforcerService.TAG, "counter: limit set aside until ${state.day.plusDays(1)}")
        persistNow()
        announceVerdict()
    }

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

    /**
     * Whether this sample is evidence of somebody being there.
     *
     * Playback running, the app in front changing, or the screen coming on. Not much, but this
     * television reports no user interaction at all, so it is what there is.
     */
    private fun somethingHappened(playing: Boolean, screenOn: Boolean, appId: String?): Boolean {
        val appChanged = appId != appDuringInterval
        val screenJustOn = screenOn && !screenOnDuringInterval
        return playing || appChanged || screenJustOn
    }

    /** What the rule in `:rules` sees, so the same picture can be logged and tested. */
    fun attention(nowMs: Long = System.currentTimeMillis()): Attention = Attention(
        screenOn = screenOnDuringInterval,
        screenSaver = screenSavers.contains(appDuringInterval),
        playing = playingDuringInterval,
        tvInput = tvInputs.contains(appDuringInterval),
        quietForMs = nowMs - lastActivityAtMs,
    )

    private fun sample(screenOnNow: Boolean, appIdNow: String?) {
        val nowMs = System.currentTimeMillis()
        val playingNow = audioManager?.isMusicActive == true
        if (somethingHappened(playingNow, screenOnNow, appIdNow)) lastActivityAtMs = nowMs

        val watching = AttentionRule.isWatching(attention(nowMs))
        announceAttention(watching, nowMs)
        val previous = state

        val result = counter.sample(previous, nowMs, watching, appDuringInterval)
        state = result.state

        screenOnDuringInterval = screenOnNow
        appDuringInterval = appIdNow
        playingDuringInterval = playingNow

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
        val stillWatching = AttentionRule.isWatching(attention(nowMs))
        val stoppedWatching = watching && !stillWatching
        if (result.addedMillis > 0 || rolled || stoppedWatching) {
            persist(nowMs, force = rolled || stoppedWatching)
        }

        announceVerdict()
    }

    /**
     * Says out loud when the counter starts or stops charging, and why.
     *
     * The reason matters more than the fact: "the screen is on but nothing has happened for
     * six minutes" is the difference between a bug and the rule working, and without this line
     * the two look identical from outside.
     */
    private fun announceAttention(watching: Boolean, nowMs: Long) {
        if (watching == wasWatching) return
        wasWatching = watching
        val seen = attention(nowMs)
        Log.i(
            EnforcerService.TAG,
            "counter: ${if (watching) "counting" else "not counting"} — screen=${seen.screenOn} " +
                "playing=${seen.playing} saver=${seen.screenSaver} input=${seen.tvInput} " +
                "quiet=${seen.quietForMs / MILLIS_PER_SECOND}s app=$appDuringInterval",
        )
    }

    private fun announceVerdict() {
        val nowMs = System.currentTimeMillis()
        judgement = engine.judge(rules(), state, appDuringInterval, nowMs)
        onJudgement(judgement)
    }

    private fun persistNow() {
        lastSavedAtMs = System.currentTimeMillis()
        val snapshot = state
        scope?.launch {
            runCatching { Settings(context).saveBudget(snapshot) }
                .onFailure { Log.w(EnforcerService.TAG, "counter: could not persist", it) }
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
