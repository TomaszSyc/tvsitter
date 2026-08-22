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

class PinCheckTest {

    private val now = 1_787_400_000_000
    private val salt = "0f1e2d3c4b5a69788796a5b4c3d2e1f0"

    /** Cheap on purpose: the iteration count is exercised in [ParentPinTest], not here. */
    private val stored = ParentPin.create("4829", salt, iterations = 1000)

    @Test
    fun `the right PIN is accepted and forgives what came before`() {
        val after = PinCheck.verify("9999", stored, PinLockout(), now)
        val accepted = PinCheck.verify("4829", stored, after.lockout, now)

        assertEquals(PinOutcome.Accepted, accepted.outcome)
        assertEquals(PinLockout(), accepted.lockout, "a failure was still counted against it")
    }

    @Test
    fun `a wrong PIN counts down the attempts`() {
        val first = PinCheck.verify("0000", stored, PinLockout(), now)

        assertEquals(PinOutcome.Wrong(PinGuard.MAX_FAILURES - 1), first.outcome)
        assertEquals(1, first.lockout.failures)
    }

    @Test
    fun `the last wrong guess says how long the wait is, not that there is nothing left`() {
        var lockout = PinLockout()
        var outcome: PinOutcome = PinOutcome.NotSet
        repeat(PinGuard.MAX_FAILURES) {
            val attempt = PinCheck.verify("0000", stored, lockout, now)
            lockout = attempt.lockout
            outcome = attempt.outcome
        }

        // "No attempts left" followed by silence is what the first draft would have shown.
        assertEquals(PinOutcome.LockedOut(PinGuard.waitFor(1) / 1000), outcome)
    }

    @Test
    fun `the change screen spends the same attempts as the lock screen`() {
        // The hole this shares one counter to close. Two counters would mean five guesses at
        // the lock screen and another five here, then another five there — a child would just
        // use whichever door was still open.
        var lockout = PinLockout()
        repeat(PinGuard.MAX_FAILURES - 1) {
            lockout = PinCheck.verify("0000", stored, lockout, now).lockout
        }

        val change = PinCheck.change("1111", "1357", stored, lockout, now)

        assertEquals(PinOutcome.LockedOut(PinGuard.waitFor(1) / 1000), change.outcome)
        assertNull(change.hash, "a locked-out attempt changed the PIN")
    }

    @Test
    fun `a wrong current PIN on the change screen shuts the lock screen too`() {
        // The same property from the other side: attempts spent here are not available there.
        var lockout = PinLockout()
        repeat(PinGuard.MAX_FAILURES) {
            lockout = PinCheck.change("0000", "1357", stored, lockout, now).lockout
        }

        assertEquals(
            PinOutcome.LockedOut(PinGuard.waitFor(1) / 1000),
            PinCheck.verify("4829", stored, lockout, now).outcome,
            "the right PIN was accepted while the keypad was supposed to be shut",
        )
    }

    @Test
    fun `a change with the right PIN produces a hash for the new one`() {
        // Also that the new hash carries its own salt rather than the old PIN's.
        val change = PinCheck.change("4829", "1357", stored, PinLockout(), now)
        val updated = checkNotNull(change.hash)

        assertEquals(PinOutcome.Accepted, change.outcome)
        assertTrue(ParentPin.matches("1357", updated))
        assertFalse(ParentPin.matches("4829", updated), "the old PIN still works")
    }

    @Test
    fun `a change carries the current iteration count, not the stored one`() {
        // A PIN set years ago under a lower count should not keep that count for ever, or
        // raising the default would never reach the households that already have a PIN.
        val old = ParentPin.create("4829", salt, iterations = 1000)
        val change = PinCheck.change("4829", "1357", old, PinLockout(), now)

        assertEquals(ParentPin.ITERATIONS, checkNotNull(change.hash).iterations)
    }

    @Test
    fun `nothing can be typed on a television with no PIN`() {
        // Deliberately not "anything is accepted" and deliberately not a way to set the first
        // PIN: on the television nothing tells a parent apart from a child except the PIN, so
        // a child would simply set one and unlock with it. The first PIN comes from Home
        // Assistant.
        assertEquals(PinOutcome.NotSet, PinCheck.verify("1234", null, PinLockout(), now).outcome)

        val change = PinCheck.change("1234", "1357", null, PinLockout(), now)
        assertEquals(PinOutcome.NotSet, change.outcome)
        assertNull(change.hash)
    }

    @Test
    fun `a stored hash that cannot be compared reads as no PIN at all`() {
        // Rather than as a PIN nothing matches, which would spend a parent's five attempts on
        // something that could never succeed and then shut the keypad for five minutes.
        val broken = PinHash(iterations = 1000, saltHex = "", hashHex = "abcd")

        val attempt = PinCheck.verify("4829", broken, PinLockout(), now)

        assertEquals(PinOutcome.NotSet, attempt.outcome)
        assertEquals(PinLockout(), attempt.lockout, "an attempt was spent on it")
    }

    @Test
    fun `an unusable new PIN is refused without spending an attempt`() {
        val change = PinCheck.change("4829", "12", stored, PinLockout(), now)

        assertEquals(PinOutcome.NewPinRejected, change.outcome)
        assertNull(change.hash)
        assertEquals(PinLockout(), change.lockout, "a typo in the new PIN cost an attempt")
    }

    @Test
    fun `a locked-out guess is not even compared`() {
        var lockout = PinLockout()
        repeat(PinGuard.MAX_FAILURES) {
            lockout = PinCheck.verify("0000", stored, lockout, now).lockout
        }
        val shut = lockout

        val correct = PinCheck.verify("4829", stored, shut, now)

        assertEquals(PinOutcome.LockedOut(PinGuard.waitFor(1) / 1000), correct.outcome)
        assertEquals(shut, correct.lockout, "the deadline moved because of a guess")
    }

    @Test
    fun `the wait runs out and the PIN works again`() {
        var lockout = PinLockout()
        repeat(PinGuard.MAX_FAILURES) {
            lockout = PinCheck.verify("0000", stored, lockout, now).lockout
        }

        val later = now + PinGuard.waitFor(1)
        assertEquals(PinOutcome.Accepted, PinCheck.verify("4829", stored, lockout, later).outcome)
    }
}
