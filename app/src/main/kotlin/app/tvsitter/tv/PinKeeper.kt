/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.tv

import android.content.Context
import android.os.Handler
import android.os.Looper
import android.util.Log
import app.tvsitter.rules.ParentPin
import app.tvsitter.rules.PinCheck
import app.tvsitter.rules.PinGuard
import app.tvsitter.rules.PinHash
import app.tvsitter.rules.PinOutcome
import app.tvsitter.rules.contract.Contract

/**
 * The parent PIN as the rest of the app sees it: ask a question, get an answer, and the
 * counter of wrong guesses is kept up to date without the caller thinking about it.
 *
 * The decisions live in [PinCheck], which is plain Kotlin and tested on the JVM. What is here
 * is the part that cannot be: reading and writing the store, and saying in the log what
 * happened without ever saying what was typed.
 *
 * Two places type a PIN — the lock screen and the change screen — and both come through here,
 * so both spend the same five attempts. A change screen with a counter of its own would be a
 * second door with no lock on it.
 */
class PinKeeper(context: Context) {

    private val store = PinStore(context)

    val isSet: Boolean get() = store.hash != null

    /** Null when the PIN has never been changed, rather than zero. */
    val changedAtMs: Long? get() = store.changedAtMs.takeIf { it > 0 }

    val changedBy: String? get() = store.changedBy

    /**
     * Checks [pin] and answers on the main thread.
     *
     * Off-thread because the derivation is slow on purpose and this television is not fast:
     * measured at 2078 ms for one verification, and a change is two of them. That is not a
     * pause, it is a lock screen that looks broken, and it sits close enough to an ANR to be
     * worth keeping away from the main thread even if it never quite got there.
     */
    fun verify(pin: String, onResult: (PinOutcome) -> Unit) {
        answerOffThread({ verify(pin) }, onResult)
    }

    /** Replaces the PIN if [current] is right, and answers on the main thread. */
    fun change(current: String, new: String, onResult: (PinOutcome) -> Unit) {
        answerOffThread({ change(current, new) }, onResult)
    }

    /**
     * A thread per entry, which sounds wasteful and is not: a PIN is typed a handful of times
     * a day, and the alternative is an executor kept alive for the life of the app to do
     * nothing at all.
     */
    private fun answerOffThread(work: () -> PinOutcome, onResult: (PinOutcome) -> Unit) {
        val main = Handler(Looper.getMainLooper())
        Thread({
            val outcome = work()
            main.post { onResult(outcome) }
        }, "pin-check").start()
    }

    /** Checks [pin] against the stored hash, spending an attempt if it is wrong. */
    private fun verify(pin: String): PinOutcome {
        val startedAtMs = System.currentTimeMillis()
        val attempt = PinCheck.verify(pin, store.hash, store.lockout, startedAtMs)
        store.lockout = attempt.lockout
        // The elapsed time is here because the hash is deliberately expensive and this runs on
        // the main thread: if a television takes long enough over it to be felt, that shows up
        // as a number rather than as a hunch.
        Log.i(
            EnforcerService.TAG,
            "pin: ${describe(attempt.outcome)} in ${System.currentTimeMillis() - startedAtMs}ms",
        )
        return attempt.outcome
    }

    /**
     * Replaces the PIN, if [current] is the one in force.
     *
     * This is the path that works with no Home Assistant at all. It cannot create a first PIN:
     * see [PinCheck.change] for why not.
     */
    private fun change(current: String, new: String): PinOutcome {
        val nowMs = System.currentTimeMillis()
        val change = PinCheck.change(current, new, store.hash, store.lockout, nowMs)
        store.lockout = change.lockout
        change.hash?.let { hash ->
            store.hash = hash
            store.changedAtMs = nowMs
            store.changedBy = Contract.PIN_SOURCE_TV
        }
        Log.i(EnforcerService.TAG, "pin: change ${describe(change.outcome)}")
        return change.outcome
    }

    /**
     * Sets or removes the PIN on Home Assistant's word, with no current PIN required.
     *
     * Not a hole: reaching this means publishing to the broker this television is paired with,
     * which is the parent's own Home Assistant. It is also the only way out of a forgotten
     * PIN, and the only way to a first one.
     */
    fun replace(hash: PinHash?) {
        if (hash != null && !ParentPin.isUsable(hash)) {
            // Refused rather than stored: a salt of the wrong shape throws inside the
            // derivation, and that would happen on the main thread with the lock on screen.
            Log.w(EnforcerService.TAG, "pin: refusing a malformed hash, leaving the PIN alone")
            return
        }
        store.hash = hash
        store.changedAtMs = System.currentTimeMillis()
        store.changedBy = Contract.PIN_SOURCE_HA
        // A new PIN forgives a run of wrong guesses at the old one, which would otherwise keep
        // the keypad shut for five minutes after the parent had already fixed the problem.
        store.lockout = PinGuard.afterSuccess()
        Log.i(
            EnforcerService.TAG,
            if (hash == null) "pin: removed from Home Assistant" else "pin: set from Home Assistant",
        )
    }

    /** Never includes the PIN, and never the hash either. */
    private fun describe(outcome: PinOutcome): String = when (outcome) {
        PinOutcome.Accepted -> "accepted"
        is PinOutcome.Wrong -> "wrong, ${outcome.attemptsRemaining} attempts left"
        is PinOutcome.LockedOut -> "refused, keypad shut for ${outcome.secondsRemaining}s"
        PinOutcome.NotSet -> "refused, no PIN on this television"
        PinOutcome.NewPinRejected -> "refused, the new PIN was not usable"
    }
}
