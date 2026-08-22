/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.rules

/** What happened to one PIN entry. */
sealed interface PinOutcome {
    data object Accepted : PinOutcome

    data class Wrong(val attemptsRemaining: Int) : PinOutcome

    data class LockedOut(val secondsRemaining: Long) : PinOutcome

    /** There is no PIN to check against, so nothing can be typed to get past this. */
    data object NotSet : PinOutcome

    /**
     * A proposed new PIN that is not four to eight digits, so nothing changed.
     *
     * Only [PinCheck.change] produces this, and only a caller that ignored the keypad's own
     * limits can trigger it. It is an outcome rather than a thrown exception because the code
     * that would throw runs inside the service that holds the lock up: a crash there takes the
     * lock down with it, which is the one failure this product cannot afford.
     */
    data object NewPinRejected : PinOutcome
}

/** An entry and the lockout state it leaves behind, which the caller has to persist. */
data class PinAttempt(val outcome: PinOutcome, val lockout: PinLockout)

/** A change attempt. [hash] is non-null only when the change was accepted. */
data class PinChange(val outcome: PinOutcome, val lockout: PinLockout, val hash: PinHash? = null)

/**
 * One PIN entry, from the check for a lockout to the state it leaves behind.
 *
 * Separate from the storage that holds the hash and the counter, so that this — where the
 * order of operations is the security property — is testable on the JVM. Both places a PIN can
 * be typed go through it: the lock screen, and the change-of-PIN screen.
 *
 * That sharing is the point rather than a convenience. A change screen with its own counter
 * would be a second oracle with unlimited guesses standing next to a keypad that allows five,
 * so a child would simply use the other door. One counter, one budget of attempts, whichever
 * screen spends them.
 */
object PinCheck {

    fun verify(pin: String, stored: PinHash?, lockout: PinLockout, nowMs: Long): PinAttempt {
        // A hash that cannot be compared against is treated as no PIN rather than as a PIN
        // nothing matches. The second reading would spend a parent's five attempts on
        // something that could never succeed, and then shut the keypad for five minutes.
        if (stored == null || !ParentPin.isUsable(stored)) {
            return PinAttempt(PinOutcome.NotSet, lockout)
        }

        // Before the comparison, so a locked-out guess is not even checked. Checking it first
        // and then refusing would still answer the question "was that the PIN" through timing.
        val verdict = PinGuard.verdict(lockout, nowMs)
        if (verdict is PinVerdict.LockedOut) {
            return PinAttempt(PinOutcome.LockedOut(verdict.secondsRemaining), lockout)
        }

        if (ParentPin.matches(pin, stored)) {
            return PinAttempt(PinOutcome.Accepted, PinGuard.afterSuccess())
        }

        // Reported from the state this failure produced, not the one before it, so the fifth
        // wrong guess says "wait five minutes" rather than "no attempts left" and then nothing.
        val failed = PinGuard.afterFailure(lockout, nowMs)
        return PinAttempt(outcomeFor(failed, nowMs), failed)
    }

    /**
     * Replaces the PIN, if [current] is the one in force.
     *
     * Requiring the current PIN is what stops this screen being the way past the lock: without
     * it, a child sets a PIN of their own and unlocks the television with it. There is
     * deliberately no path here that creates a first PIN — on the television nothing
     * distinguishes a parent from a child except knowing the PIN, so the first one has to come
     * from Home Assistant.
     */
    fun change(current: String, new: String, stored: PinHash?, lockout: PinLockout, nowMs: Long): PinChange {
        // Before spending an attempt, and before the two hashes this would otherwise compute:
        // a PIN that could not be stored anyway is not worth checking the current one for.
        if (!ParentPin.isPlausible(new)) return PinChange(PinOutcome.NewPinRejected, lockout)

        val attempt = verify(current, stored, lockout, nowMs)
        if (attempt.outcome != PinOutcome.Accepted) {
            return PinChange(attempt.outcome, attempt.lockout)
        }
        // A fresh salt, not the one the old PIN used: reusing it would mean an attacker
        // holding both files could tell that the PIN had changed and rule out the old one.
        return PinChange(PinOutcome.Accepted, attempt.lockout, ParentPin.create(new))
    }

    private fun outcomeFor(state: PinLockout, nowMs: Long): PinOutcome =
        when (val verdict = PinGuard.verdict(state, nowMs)) {
            is PinVerdict.LockedOut -> PinOutcome.LockedOut(verdict.secondsRemaining)
            is PinVerdict.Open -> PinOutcome.Wrong(verdict.attemptsRemaining)
        }
}
