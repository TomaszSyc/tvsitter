/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.rules

import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Test

class PinGuardTest {

    private val now = 1_787_400_000_000

    @Test
    fun `a fresh keypad offers every attempt`() {
        assertEquals(PinVerdict.Open(PinGuard.MAX_FAILURES), PinGuard.verdict(PinLockout(), now))
    }

    @Test
    fun `wrong guesses count down and then shut the keypad`() {
        var state = PinLockout()
        repeat(PinGuard.MAX_FAILURES - 1) { state = PinGuard.afterFailure(state, now) }

        assertEquals(PinVerdict.Open(1), PinGuard.verdict(state, now))

        state = PinGuard.afterFailure(state, now)
        assertEquals(PinVerdict.LockedOut(300), PinGuard.verdict(state, now))
    }

    @Test
    fun `the lockout runs out and the count goes with it`() {
        var state = PinLockout()
        repeat(PinGuard.MAX_FAILURES) { state = PinGuard.afterFailure(state, now) }

        assertEquals(PinVerdict.LockedOut(300), PinGuard.verdict(state, now))
        assertEquals(PinVerdict.LockedOut(1), PinGuard.verdict(state, now + PinGuard.LOCKOUT_MS - 1))

        // Not merely open again, but open with the full count. Carrying the failures over would
        // mean the next wrong guess shuts it for another five minutes, and the one after that,
        // for as long as somebody keeps getting it wrong — which is a parent who has forgotten
        // their PIN, locked out of their own television for good.
        assertEquals(
            PinVerdict.Open(PinGuard.MAX_FAILURES),
            PinGuard.verdict(state, now + PinGuard.LOCKOUT_MS),
        )
    }

    @Test
    fun `guessing while locked out does not extend the lockout`() {
        var state = PinLockout()
        repeat(PinGuard.MAX_FAILURES) { state = PinGuard.afterFailure(state, now) }
        val locked = state

        // A child hammering the keypad must not be able to keep it shut indefinitely, which
        // would lock the parent out along with them.
        repeat(10) { press -> state = PinGuard.afterFailure(state, now + 1000L * press) }

        assertEquals(locked.lockedUntilMs, state.lockedUntilMs, "the deadline moved")
    }

    @Test
    fun `the right PIN forgives what came before it`() {
        var state = PinLockout()
        repeat(PinGuard.MAX_FAILURES - 1) { state = PinGuard.afterFailure(state, now) }

        assertEquals(PinLockout(), PinGuard.afterSuccess())
        assertEquals(PinVerdict.Open(PinGuard.MAX_FAILURES), PinGuard.verdict(PinGuard.afterSuccess(), now))
    }
}
