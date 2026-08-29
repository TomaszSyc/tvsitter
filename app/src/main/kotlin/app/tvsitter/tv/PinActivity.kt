/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.tv

import android.app.Activity
import android.content.Intent
import android.graphics.Color
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.util.TypedValue
import android.view.Gravity
import android.view.WindowManager
import android.widget.FrameLayout
import android.widget.TextView
import app.tvsitter.rules.ParentPin
import app.tvsitter.rules.PinOutcome

/**
 * Changing the parent PIN at the television, with no Home Assistant involved.
 *
 * This exists for the evening Home Assistant is not there: a dead SD card, a broker that will
 * not start, a house move. The PIN is the only thing that lifts a lock at the set itself, so
 * being unable to change it because the other half of the product is down would mean a PIN a
 * child has watched being typed stays in force indefinitely.
 *
 * The current PIN is required, and that is what keeps this from being the way past the lock.
 * There is deliberately no path here that sets a *first* PIN — see [app.tvsitter.rules.PinCheck].
 *
 * The new PIN is typed twice because the keypad is masked. A single masked entry means a typo
 * locks the parent out of their own television, in the exact situation where Home Assistant is
 * not available to put it right.
 *
 * Both PINs sit in memory as strings while the flow runs, which is not worth pretending
 * otherwise about: anyone able to read this process's heap can read the stored hash too. What
 * matters is that neither is written down or logged.
 */
class PinActivity : Activity() {

    private enum class Step { CURRENT, NEW, CONFIRM }

    private lateinit var pin: PinKeeper
    private var keypad: PinKeypad? = null
    private var step = Step.CURRENT
    private var currentPin = ""
    private var proposed = ""

    /**
     * What a correct PIN is being asked for. Changing it is the original job; opening a pairing
     * window is the other, because a pairing code on a fifty-inch screen hands the television to
     * whoever is holding the remote (#98).
     */
    private val forPairing: Boolean by lazy { intent?.getBooleanExtra(EXTRA_FOR_PAIRING, false) == true }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        // Three questions in a row, each with a couple of seconds of hashing between them, is
        // long enough for a television to decide nobody is there.
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        pin = PinKeeper(this)

        if (!pin.isSet) {
            // Nothing to ask for. A television with no PIN has nobody to keep out of pairing
            // either, which is the first run and is meant to be open.
            if (forPairing) {
                EnforcerService.instance?.requestPairing()
                finish()
                return
            }
            showNote(getString(R.string.pin_from_ha))
            return
        }

        val pad = PinKeypad(this, onSubmit = ::onTyped, onCancel = { finish() })
        keypad = pad
        setContentView(
            FrameLayout(this).apply {
                setBackgroundColor(BACKDROP)
                descendantFocusability = FrameLayout.FOCUS_AFTER_DESCENDANTS
                addView(
                    pad,
                    FrameLayout.LayoutParams(
                        FrameLayout.LayoutParams.WRAP_CONTENT,
                        FrameLayout.LayoutParams.WRAP_CONTENT,
                        Gravity.CENTER,
                    ),
                )
            },
        )
        ask(Step.CURRENT)
        pad.focusKeypad()
    }

    /**
     * Leaves rather than waits.
     *
     * Halfway through, this screen is holding a PIN that has already been proved. Coming back
     * to it after the television has been off for an hour should not carry on from there, and
     * the cost of starting again is four button presses.
     */
    override fun onPause() {
        super.onPause()
        if (!isFinishing) finish()
    }

    private fun onTyped(typed: String) {
        when (step) {
            Step.CURRENT -> checkCurrent(typed)
            Step.NEW -> takeNew(typed)
            Step.CONFIRM -> confirm(typed)
        }
    }

    /**
     * Checked here rather than only at the end, so a wrong PIN is answered before the parent
     * types a new one twice. It costs an attempt either way; this way it costs less patience.
     */
    private fun checkCurrent(typed: String) {
        keypad?.message(getString(R.string.pin_checking))
        pin.verify(typed) { outcome ->
            if (outcome != PinOutcome.Accepted) {
                keypad?.message(pinMessage(outcome).orEmpty())
                return@verify
            }
            if (forPairing) {
                // Nothing is remembered and nothing is hashed again: the question was only
                // whether the person at the keypad is the one the PIN is for.
                EnforcerService.instance?.requestPairing()
                finish()
                return@verify
            }
            currentPin = typed
            ask(Step.NEW)
        }
    }

    private fun takeNew(typed: String) {
        // The keypad cannot produce anything else, so this is a second pair of eyes rather
        // than the check that matters.
        if (!ParentPin.isPlausible(typed)) {
            keypad?.message(getString(R.string.pin_length, ParentPin.LENGTH))
            return
        }
        proposed = typed
        ask(Step.CONFIRM)
    }

    private fun confirm(typed: String) {
        if (typed != proposed) {
            // Back to the new PIN rather than to the beginning: the current one has already
            // been proved, and asking for it again answers a typo with another round of it.
            proposed = ""
            ask(Step.NEW)
            keypad?.message(getString(R.string.pin_mismatch))
            return
        }

        keypad?.message(getString(R.string.pin_checking))
        // Two derivations here, one to check the current PIN and one to hash the new: about
        // four seconds on this television, which is why none of it runs on the main thread.
        pin.change(currentPin, proposed) { outcome ->
            currentPin = ""
            proposed = ""
            if (outcome == PinOutcome.Accepted) {
                announceToHomeAssistant()
                showNote(getString(R.string.pin_changed))
                // Long enough to be read from a sofa, then out of the way without a button.
                Handler(Looper.getMainLooper()).postDelayed({ finish() }, DONE_MS)
                return@change
            }

            // Reachable: the lockout can begin between the first step and this one, if
            // somebody was guessing at the lock screen in between.
            ask(Step.CURRENT)
            keypad?.message(pinMessage(outcome).orEmpty())
        }
    }

    /**
     * Tells Home Assistant the PIN changed, as soon as there is a broker to tell.
     *
     * Only that it changed, and when: the hash stays on the television. If the broker is
     * unreachable the state payload is retained, so it lands on the next connect rather than
     * being lost — which is the case this whole screen exists for.
     */
    private fun announceToHomeAssistant() {
        startForegroundService(
            Intent(this, EnforcerService::class.java).setAction(EnforcerService.ACTION_PUBLISH),
        )
    }

    private fun ask(next: Step) {
        step = next
        keypad?.prompt(
            getString(
                when {
                    next == Step.CURRENT && forPairing -> R.string.pin_step_pairing
                    next == Step.CURRENT -> R.string.pin_step_current
                    next == Step.NEW -> R.string.pin_step_new
                    else -> R.string.pin_step_confirm
                },
            ),
        )
    }

    /** For the two dead ends: nothing to change, and nothing left to do. */
    private fun showNote(text: String) {
        keypad = null
        setContentView(
            TextView(this).apply {
                this.text = text
                setTextColor(Color.WHITE)
                setBackgroundColor(BACKDROP)
                setTextSize(TypedValue.COMPLEX_UNIT_SP, NOTE_SP)
                gravity = Gravity.CENTER
                setPadding(PADDING, PADDING, PADDING, PADDING)
            },
        )
    }

    companion object {
        /** Ask for the PIN, then open a pairing window rather than changing anything. */
        const val EXTRA_FOR_PAIRING: String = "for_pairing"

        private const val BACKDROP = 0xFF0B1017.toInt()
        private const val NOTE_SP = 24f
        private const val PADDING = 48
        private const val DONE_MS = 2500L
    }
}
