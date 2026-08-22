/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.rules

/** How many wrong guesses there have been, and until when the keypad is shut. */
data class PinLockout(val failures: Int = 0, val lockedUntilMs: Long = 0)

/** Whether the keypad will take a guess at all. */
sealed interface PinVerdict {
    data class Open(val attemptsRemaining: Int) : PinVerdict

    data class LockedOut(val secondsRemaining: Long) : PinVerdict
}

/**
 * Counting wrong guesses at the parent PIN.
 *
 * A four-digit code with unlimited guesses is not a secret, and this is the control that
 * actually protects it — hashing protects the stored file, not the PIN against a child with a
 * remote and an afternoon. Ten thousand guesses at five per five minutes is nineteen years.
 *
 * Timed rather than permanent, unlike pairing. A pairing window that runs out of attempts is
 * replaced by opening a new one; a parent locked out of their own television for good would
 * have to reinstall the app, which is a worse outcome than a wait.
 *
 * The state is returned rather than held so the caller can persist it. That is not tidiness:
 * without persistence, force-stopping the app resets the counter, and force-stopping an app is
 * something a child can do from Settings.
 */
object PinGuard {

    const val MAX_FAILURES: Int = 5

    /** Long enough to be discouraging, short enough that a parent will wait it out. */
    const val LOCKOUT_MS: Long = 5 * 60 * 1000

    private const val MILLIS_PER_SECOND = 1000L

    fun verdict(state: PinLockout, nowMs: Long): PinVerdict {
        val remaining = state.lockedUntilMs - nowMs
        if (remaining > 0) {
            return PinVerdict.LockedOut(
                secondsRemaining = (remaining + MILLIS_PER_SECOND - 1) / MILLIS_PER_SECOND,
            )
        }
        // Past the deadline, so the failures that caused it are spent too. Keeping them would
        // mean the next wrong guess shuts the keypad again immediately, and the one after
        // that, for as long as somebody keeps getting it wrong.
        return PinVerdict.Open(attemptsRemaining = MAX_FAILURES - state.failures)
    }

    fun afterFailure(state: PinLockout, nowMs: Long): PinLockout {
        // Already shut, so this guess changes nothing. Counting it moved the deadline out by
        // another five minutes per press, which let a child hammering the keypad keep it shut
        // indefinitely — and kept the parent out with them.
        if (state.lockedUntilMs > nowMs) return state

        val failures = state.failures + 1
        return if (failures >= MAX_FAILURES) {
            PinLockout(failures = 0, lockedUntilMs = nowMs + LOCKOUT_MS)
        } else {
            PinLockout(failures = failures, lockedUntilMs = 0)
        }
    }

    /** A correct PIN forgives everything before it. */
    fun afterSuccess(): PinLockout = PinLockout()
}
