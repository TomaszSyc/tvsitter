/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.rules

/**
 * Why the lock was up, if it was.
 *
 * Kept because a restart has to tell them apart: restored as a budget lock it lifts as soon as
 * there is time again, and restored as a manual one it stays until a parent lifts it.
 */
enum class LockCause { NONE, BUDGET, MANUAL }

/**
 * Everything that decides whether the television is covered.
 *
 * A data class in `:rules` rather than four fields in the service, because this is where a
 * mistake means a permanently locked or a permanently unlocked television, and until now it was
 * checked by hand on hardware one case at a time. Five bugs came out of it that way (#43).
 *
 * The side effects — the overlay, the banner, audio focus, what gets written to storage — are
 * not here. The caller compares the state before against the state after and acts on the
 * difference, which is what makes the interleaving of "refuse to hide a budget lock" and "stand
 * the limit down first" something a JVM test can pin down.
 */
data class LockState(
    /** A parent's decision. Stays true while the lock stands down for granted time. */
    val manual: Boolean = false,
    /** The rules say viewing has to stop. Worked out again from the counter after a restart. */
    val budget: Boolean = false,
    /** Until when a manual lock is standing down, epoch millis. Zero when it is not. */
    val pausedUntilMs: Long = 0,
    /** The last decision acted on, so that the same one arriving again changes nothing. */
    val lastDecision: Decision? = null,
) {
    /**
     * Whether a lock a parent asked for is in force *now*.
     *
     * Not the same as [manual], which stays true through granted time. Everything deciding
     * whether to cover the screen asks this; only granting and unlocking touch the other.
     */
    fun manualInForce(nowMs: Long): Boolean = manual && pausedUntilMs <= nowMs

    fun covered(nowMs: Long): Boolean = budget || manualInForce(nowMs)

    /**
     * What to remember across a reboot.
     *
     * A manual lock outranks a budget one even while it is standing down, and that ordering is
     * the whole point. Writing BUDGET over a manual lock — which the old code did whenever a
     * spent budget arrived during granted time — meant a restart restored a lock that lifted by
     * itself as soon as there was time again, and the parent's decision was gone. The same
     * family of mistake as #66, one path along.
     */
    val cause: LockCause
        get() = when {
            manual -> LockCause.MANUAL
            budget -> LockCause.BUDGET
            else -> LockCause.NONE
        }
}

/** What the caller has to do about a transition. Null effects mean: change nothing at all. */
data class LockEffects(
    val covered: Boolean,
    /** Seconds left, to be said out loud as a warning. Null means no warning is due. */
    val warnAtRemainingSeconds: Long? = null,
    /** A package to send to the background, which is not the same as covering the screen. */
    val displace: String? = null,
    /** Set the day's limit aside until the next reset, because the lock it put up was lifted. */
    val standDownLimit: Boolean = false,
)

data class LockChange(val state: LockState, val effects: LockEffects?)

/**
 * Every way the lock can change, as pure functions.
 *
 * Each returns the new state and what to do about it. Nothing here reads a clock, opens a
 * window or writes a file: the times come in as arguments precisely so that the awkward cases —
 * a grant arriving while the budget is also spent, a reboot in the middle of granted time — are
 * testable without a television.
 */
object LockTransitions {

    private const val MILLIS_PER_SECOND = 1_000L

    /**
     * Acts on what the rules say, but only when the answer has changed.
     *
     * Sampling runs every ten seconds and the answer is usually the same as last time.
     * Re-showing the warning on each one would put a banner on screen permanently for the last
     * five minutes of the day, which is nagging rather than warning. The comparison is on the
     * decision and not the whole judgement, because the seconds remaining differ every sample —
     * comparing those would nag anyway, and comparing only the verdict would collapse a
     * quarter-hour warning and a five-minute one into one warning (#39).
     */
    fun applyDecision(state: LockState, judgement: Judgement, nowMs: Long): LockChange {
        if (judgement.decision == state.lastDecision) return LockChange(state, null)

        // Anything that is not SPENT means there is time, so a budget lock has to lift —
        // including WARN. Treating WARN as merely "show a banner" left the lock up after a
        // grant of a few minutes: there was time again, a warning about it was on screen, and
        // the television stayed covered.
        val next = state.copy(
            budget = judgement.state == BudgetVerdict.SPENT,
            lastDecision = judgement.decision,
        )
        val covered = next.covered(nowMs)
        return LockChange(
            next,
            LockEffects(
                covered = covered,
                warnAtRemainingSeconds = judgement.remainingSeconds.takeIf {
                    judgement.state == BudgetVerdict.WARN
                },
                // Behind a covered screen there is nothing to displace, and displacing anyway
                // would fight the launcher the lock is already sitting on.
                displace = judgement.decision.displaceApp.takeUnless { covered },
            ),
        )
    }

    /**
     * A parent locked the television.
     *
     * A fresh lock overrides time granted earlier: locking now means now, not once the last
     * fifteen minutes have run out.
     */
    fun lockManually(state: LockState): LockChange {
        val next = state.copy(manual = true, pausedUntilMs = 0, lastDecision = null)
        return LockChange(next, LockEffects(covered = true))
    }

    /**
     * A parent lifted their own lock.
     *
     * Does not lift a budget lock: the overlay would come straight back on the next sample and
     * look broken. Granting time is how that one is answered, which is why `unlock` carrying
     * minutes means something different from `unlock` on its own.
     */
    fun unlockManually(state: LockState, nowMs: Long): LockChange {
        val next = state.copy(manual = false, pausedUntilMs = 0, lastDecision = null)
        return LockChange(next, LockEffects(covered = next.covered(nowMs)))
    }

    /**
     * The answer both to `unlock` with no minutes and to a correct PIN, which have to mean the
     * same thing.
     *
     * Setting the limit aside either way meant that lifting a bedtime lock also handed over the
     * rest of the day's budget, which is not what the person doing it asked for (#42). Hiding a
     * budget lock *without* setting the limit aside does not work either: the next sample would
     * put it straight back, ten seconds later, for no reason a child could be told. So the
     * limit stands down only when the limit is what put the lock there, and the screen comes
     * off on the next decision rather than here.
     */
    fun unlockUntilReset(state: LockState, nowMs: Long): LockChange {
        val unlocked = unlockManually(state, nowMs)
        return LockChange(
            unlocked.state,
            LockEffects(covered = unlocked.state.covered(nowMs), standDownLimit = state.budget),
        )
    }

    /**
     * A parent granted time, so a manual lock stands down and comes back when the time is up.
     *
     * It stands down rather than ending, because "+15 min" has to mean fifteen minutes. Nothing
     * happens to a television nobody locked: the budget half of a grant is the bonus the caller
     * adds, which the next decision picks up on its own.
     */
    fun standDownFor(state: LockState, seconds: Long, nowMs: Long): LockChange {
        if (!state.manual) return LockChange(state, null)

        val next = state.copy(pausedUntilMs = nowMs + seconds * MILLIS_PER_SECOND, lastDecision = null)
        return LockChange(next, LockEffects(covered = next.covered(nowMs)))
    }

    /** The granted time is up. The lock comes back if it was a parent's, and not otherwise. */
    fun resumeAfterStandDown(state: LockState, nowMs: Long): LockChange {
        val next = state.copy(pausedUntilMs = 0, lastDecision = null)
        return LockChange(next, LockEffects(covered = next.covered(nowMs)))
    }

    /**
     * Puts the lock back after a restart, from the little that is remembered.
     *
     * Granted time survives a reboot too, so a manual lock whose stand-down has not expired
     * comes back uncovered — showing the lock here would take back minutes a parent had already
     * given. A budget lock needs no deadline: the counter and the rules work it out again.
     */
    fun restore(cause: LockCause, pausedUntilMs: Long, nowMs: Long): LockChange {
        val state = when (cause) {
            LockCause.MANUAL -> LockState(manual = true, pausedUntilMs = pausedUntilMs)
            LockCause.BUDGET -> LockState(budget = true)
            LockCause.NONE -> LockState()
        }
        return LockChange(state, LockEffects(covered = state.covered(nowMs)))
    }
}
