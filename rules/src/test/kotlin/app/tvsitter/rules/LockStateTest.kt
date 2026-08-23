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

class LockStateTest {

    private val now = 1_787_400_000_000
    private val minute = 60_000L

    private val nothing = LockState()

    private fun verdict(
        state: BudgetVerdict,
        remainingSeconds: Long? = null,
        reason: LockReason = LockReason.DAILY_LIMIT,
        warnAtSeconds: Long? = null,
        displaceApp: String? = null,
    ) = Judgement(
        Decision(state, reason, warnAtSeconds, displaceApp = displaceApp),
        remainingSeconds = remainingSeconds,
    )

    @Test
    fun `nothing locked is nothing covered`() {
        assertFalse(nothing.covered(now))
        assertEquals(LockCause.NONE, nothing.cause)
    }

    @Test
    fun `a spent day covers the screen`() {
        val change = LockTransitions.applyDecision(nothing, verdict(BudgetVerdict.SPENT, 0), now)

        assertTrue(change.effects!!.covered)
        assertEquals(LockCause.BUDGET, change.state.cause)
    }

    @Test
    fun `anything that is not spent lifts a budget lock, warnings included`() {
        // The first bug this class produced. Treating WARN as merely "show a banner" left the
        // lock up after a grant of a few minutes: there was time again, a warning about it was
        // on screen, and the television stayed covered.
        val locked = LockTransitions.applyDecision(nothing, verdict(BudgetVerdict.SPENT, 0), now).state

        val warned = LockTransitions.applyDecision(
            locked,
            verdict(BudgetVerdict.WARN, 240, warnAtSeconds = 300),
            now,
        )

        assertFalse(warned.effects!!.covered)
        assertEquals(240, warned.effects.warnAtRemainingSeconds)
    }

    @Test
    fun `the same answer arriving again changes nothing at all`() {
        // Sampling every ten seconds, and re-showing the warning on each one would put a banner
        // on screen permanently for the last five minutes of the day.
        val warned = verdict(BudgetVerdict.WARN, 300, warnAtSeconds = 300)
        val first = LockTransitions.applyDecision(nothing, warned, now)

        val again = LockTransitions.applyDecision(first.state, warned, now + 10_000)

        assertNull(again.effects, "nothing to do, and nothing to redraw")
        assertEquals(first.state, again.state)
    }

    @Test
    fun `a countdown ticking is not a new answer`() {
        // What makes the comparison the decision rather than the whole judgement: the seconds
        // differ every sample, so comparing those would nag exactly as badly.
        val first = LockTransitions.applyDecision(
            nothing,
            verdict(BudgetVerdict.WARN, 300, warnAtSeconds = 300),
            now,
        )

        val ticked = LockTransitions.applyDecision(
            first.state,
            verdict(BudgetVerdict.WARN, 290, warnAtSeconds = 300),
            now + 10_000,
        )

        assertNull(ticked.effects)
    }

    @Test
    fun `a second warning is a second answer`() {
        // And what makes it the decision rather than the verdict: both of these are WARN.
        val quarter = LockTransitions.applyDecision(
            nothing,
            verdict(BudgetVerdict.WARN, 900, warnAtSeconds = 900),
            now,
        )

        val five = LockTransitions.applyDecision(
            quarter.state,
            verdict(BudgetVerdict.WARN, 300, warnAtSeconds = 300),
            now + 10 * minute,
        )

        assertEquals(300, five.effects!!.warnAtRemainingSeconds)
    }

    @Test
    fun `a parent's lock outlasts the budget having time again`() {
        val locked = LockTransitions.lockManually(nothing).state

        val change = LockTransitions.applyDecision(locked, verdict(BudgetVerdict.WITHIN), now)

        assertTrue(change.effects!!.covered, "a parent's decision is not a calculation")
    }

    @Test
    fun `unlocking by hand does not lift a budget lock`() {
        // The overlay would come straight back on the next sample and look broken. Granting time
        // is how that one is answered.
        val spent = LockTransitions.applyDecision(nothing, verdict(BudgetVerdict.SPENT, 0), now).state

        val change = LockTransitions.unlockManually(spent, now)

        assertTrue(change.effects!!.covered)
        assertFalse(change.state.manual)
    }

    @Test
    fun `a correct PIN sets the day's limit aside when the limit is what locked it`() {
        val spent = LockTransitions.applyDecision(nothing, verdict(BudgetVerdict.SPENT, 0), now).state

        val change = LockTransitions.unlockUntilReset(spent, now)

        assertTrue(change.effects!!.standDownLimit)
    }

    @Test
    fun `lifting a bedtime lock does not hand over the day's budget`() {
        // #42. The same gesture, and it must not mean the same thing.
        val bedtime = LockTransitions.lockManually(nothing).state

        val change = LockTransitions.unlockUntilReset(bedtime, now)

        assertFalse(change.effects!!.standDownLimit)
        assertFalse(change.effects.covered)
    }

    @Test
    fun `a grant stands a manual lock down and the screen comes off`() {
        val locked = LockTransitions.lockManually(nothing).state

        val change = LockTransitions.standDownFor(locked, seconds = 900, nowMs = now)

        assertFalse(change.effects!!.covered)
        assertTrue(change.state.manual, "still a parent's lock, just not in force")
        assertEquals(now + 15 * minute, change.state.pausedUntilMs)
    }

    @Test
    fun `a manual lock standing down is still a manual lock`() {
        // #66. Writing NONE here threw the parent's decision away: the screen came off, the
        // memory said there was nothing to restore, and a restart left the television unlocked.
        val standing = LockTransitions.standDownFor(
            LockTransitions.lockManually(nothing).state,
            seconds = 900,
            nowMs = now,
        ).state

        assertEquals(LockCause.MANUAL, standing.cause)
        assertFalse(standing.covered(now))
        assertTrue(standing.covered(now + 16 * minute), "and it comes back")
    }

    @Test
    fun `a spent budget during granted time does not overwrite the parent's decision`() {
        // The same family as #66, one path along: the old code wrote BUDGET whenever a spent
        // budget arrived while a manual lock was standing down. A restart then restored a lock
        // that lifts by itself as soon as there is time, and the parent's decision was gone.
        val standing = LockTransitions.standDownFor(
            LockTransitions.lockManually(nothing).state,
            seconds = 900,
            nowMs = now,
        ).state

        val spent = LockTransitions.applyDecision(standing, verdict(BudgetVerdict.SPENT, 0), now + minute)

        assertEquals(LockCause.MANUAL, spent.state.cause)
        assertTrue(spent.state.manual)
    }

    @Test
    fun `a grant while the budget is also spent leaves the screen covered`() {
        // The caller's bonus is what answers the budget half; this half must not uncover a
        // television that still has no time.
        val both = LockTransitions.applyDecision(
            LockTransitions.lockManually(nothing).state,
            verdict(BudgetVerdict.SPENT, 0),
            now,
        ).state

        val change = LockTransitions.standDownFor(both, seconds = 900, nowMs = now)

        assertTrue(change.effects!!.covered)
    }

    @Test
    fun `when the granted time is up the lock comes back`() {
        val standing = LockTransitions.standDownFor(
            LockTransitions.lockManually(nothing).state,
            seconds = 900,
            nowMs = now,
        ).state

        val change = LockTransitions.resumeAfterStandDown(standing, now + 15 * minute)

        assertTrue(change.effects!!.covered)
        assertEquals(0, change.state.pausedUntilMs)
    }

    @Test
    fun `a grant on a television nobody locked changes nothing here`() {
        val change = LockTransitions.standDownFor(nothing, seconds = 900, nowMs = now)

        assertNull(change.effects)
        assertEquals(nothing, change.state)
    }

    @Test
    fun `a fresh lock overrides time granted earlier`() {
        // Locking now means now, not once the last fifteen minutes have run out.
        val standing = LockTransitions.standDownFor(
            LockTransitions.lockManually(nothing).state,
            seconds = 900,
            nowMs = now,
        ).state

        val change = LockTransitions.lockManually(standing)

        assertTrue(change.effects!!.covered)
        assertEquals(0, change.state.pausedUntilMs)
    }

    @Test
    fun `a reboot in the middle of granted time does not take the minutes back`() {
        val change = LockTransitions.restore(LockCause.MANUAL, pausedUntilMs = now + 5 * minute, nowMs = now)

        assertFalse(change.effects!!.covered)
        assertTrue(change.state.manual)
    }

    @Test
    fun `a reboot after the granted time restores the lock`() {
        val change = LockTransitions.restore(LockCause.MANUAL, pausedUntilMs = now - minute, nowMs = now)

        assertTrue(change.effects!!.covered)
    }

    @Test
    fun `a restored budget lock lifts as soon as there is time`() {
        val restored = LockTransitions.restore(LockCause.BUDGET, pausedUntilMs = 0, nowMs = now).state

        val change = LockTransitions.applyDecision(restored, verdict(BudgetVerdict.WITHIN), now)

        assertFalse(change.effects!!.covered)
    }

    @Test
    fun `restoring nothing covers nothing`() {
        val change = LockTransitions.restore(LockCause.NONE, pausedUntilMs = 0, nowMs = now)

        assertFalse(change.effects!!.covered)
        assertEquals(LockState(), change.state)
    }

    @Test
    fun `an app is not displaced from behind a lock`() {
        // There is nothing to displace behind a covered screen, and trying would be a fight
        // with the launcher the lock is already sitting on.
        val locked = LockTransitions.lockManually(nothing).state

        val change = LockTransitions.applyDecision(
            locked,
            verdict(BudgetVerdict.WITHIN, reason = LockReason.APP_LIMIT, displaceApp = NETFLIX),
            now,
        )

        assertNull(change.effects!!.displace)
    }

    @Test
    fun `an app out of its own time is displaced while the screen stays clear`() {
        val change = LockTransitions.applyDecision(
            nothing,
            verdict(BudgetVerdict.WITHIN, reason = LockReason.APP_LIMIT, displaceApp = NETFLIX),
            now,
        )

        assertEquals(NETFLIX, change.effects!!.displace)
        assertFalse(change.effects.covered)
    }

    private companion object {
        const val NETFLIX = "com.netflix.ninja"
    }
}
