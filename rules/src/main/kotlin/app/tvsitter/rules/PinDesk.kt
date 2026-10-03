/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.rules

/** Where the parent PIN and the count of wrong guesses at it are kept. */
interface PinLedger {
    var hash: PinHash?
    var lockout: PinLockout
}

/** One entry as it reached the ledger, and whether it was the one that shut the keypad. */
data class PinEntry(val outcome: PinOutcome, val lockout: PinLockout, val shutTheKeypad: Boolean)

/**
 * [PinCheck] against a stored counter, one entry at a time.
 *
 * Reading the counter, deriving the hash and writing the counter back are one step. The keypad
 * clears after every submit, so guesses typed while the previous one was still being derived —
 * two seconds on the television — each read the same count, and the fifth wrong guess never came.
 * Every desk over the same ledger has to share [lock], so the lock screen and the change screen
 * queue behind each other too.
 */
class PinDesk(private val ledger: PinLedger, private val lock: Any, private val clock: () -> Long) {

    fun verify(pin: String): PinEntry = synchronized(lock) {
        val nowMs = clock()
        val before = ledger.lockout
        val attempt = PinCheck.verify(pin, ledger.hash, before, nowMs)
        ledger.lockout = attempt.lockout
        PinEntry(attempt.outcome, attempt.lockout, shut(before, attempt.lockout, nowMs))
    }

    /** Replaces the PIN if [current] is the one in force; see [PinCheck.change]. */
    fun change(current: String, new: String): PinEntry = synchronized(lock) {
        val nowMs = clock()
        val before = ledger.lockout
        val change = PinCheck.change(current, new, ledger.hash, before, nowMs)
        ledger.lockout = change.lockout
        change.hash?.let { ledger.hash = it }
        PinEntry(change.outcome, change.lockout, shut(before, change.lockout, nowMs))
    }

    /** Sets or removes the PIN with no current one required, forgiving any run of wrong guesses. */
    fun replace(hash: PinHash?) = synchronized(lock) {
        ledger.hash = hash
        ledger.lockout = PinGuard.afterSuccess()
    }

    // Once per lockout, not once per press: the alarm is that the keypad shut, and five messages
    // for five guesses is how a parent learns to swipe them away.
    private fun shut(before: PinLockout, after: PinLockout, nowMs: Long): Boolean =
        before.lockedUntilMs <= nowMs && after.lockedUntilMs > nowMs
}
