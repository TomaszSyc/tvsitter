/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.rules

/**
 * How many wrong guesses there have been, until when the keypad is shut, and how many times in
 * a row it has come to that. The last one is what makes the wait grow.
 */
data class PinLockout(val failures: Int = 0, val lockedUntilMs: Long = 0, val lockouts: Int = 0)

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

    /**
     * Five minutes, then fifteen, then half an hour, and no longer than that.
     *
     * A flat five minutes was enough when a PIN could be eight digits. At four it is not: ten
     * thousand candidates at five tries per five minutes is about a week of solid guessing,
     * which a determined teenager has. Growing the wait turns the same ten thousand into more
     * than a month, and the ceiling is there so a parent who has forgotten their own PIN is
     * never shut out for longer than they would wait.
     */
    val LOCKOUT_LADDER_MS: List<Long> =
        listOf(FIRST_WAIT_MIN, SECOND_WAIT_MIN, LONGEST_WAIT_MIN).map { it * MILLIS_PER_MINUTE }

    private const val MILLIS_PER_SECOND = 1000L
    private const val SECONDS_PER_MINUTE = 60L
    private const val MILLIS_PER_MINUTE = SECONDS_PER_MINUTE * MILLIS_PER_SECOND

    // Constants rather than a list, because a `val` declared below the property that reads it
    // is still empty when that property initialises.
    private const val FIRST_WAIT_MIN = 5L
    private const val SECOND_WAIT_MIN = 15L
    private const val LONGEST_WAIT_MIN = 30L

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
        // another wait per press, which let a child hammering the keypad keep it shut
        // indefinitely — and kept the parent out with them.
        if (state.lockedUntilMs > nowMs) return state

        val failures = state.failures + 1
        if (failures < MAX_FAILURES) {
            return state.copy(failures = failures, lockedUntilMs = 0)
        }

        val lockouts = state.lockouts + 1
        return PinLockout(
            failures = 0,
            lockedUntilMs = nowMs + waitFor(lockouts),
            lockouts = lockouts,
        )
    }

    /** How long the [n]th consecutive lockout lasts. */
    fun waitFor(n: Int): Long = LOCKOUT_LADDER_MS[(n - 1).coerceIn(0, LOCKOUT_LADDER_MS.lastIndex)]

    /** A correct PIN forgives everything before it, the ladder included. */
    fun afterSuccess(): PinLockout = PinLockout()
}
