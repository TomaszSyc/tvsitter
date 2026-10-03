/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.tv

import android.content.Context
import android.view.Gravity
import android.view.KeyEvent
import android.widget.LinearLayout
import app.tvsitter.rules.ParentPin

/**
 * Typing a PIN with a remote control, in the shape Google TV uses for its own PIN.
 *
 * Up and down move between rows of three digits; left, centre and right pick one of the three
 * in the row showing. The rows either side sit faded above and below it so the layout can be
 * learned rather than hunted for. Two presses per digit, usually.
 *
 * There is no confirm button and no delete button, for the same reason the platform has
 * neither: the fourth digit submits, and back deletes. That only works because a PIN is
 * exactly four digits (see [ParentPin.LENGTH]) — with a range, nothing could know when the
 * entry was finished.
 *
 * The first attempt at this was a grid of nine buttons, and it leaked the PIN it was meant to
 * hide: the focus highlight follows the remote, so a child watching a fifty-inch screen reads
 * the code off it digit by digit. This shape does not have that problem, and the reason is
 * worth stating precisely — **the screen shows which row is in play and never which of the
 * three was taken**, because that choice is a direction on the remote rather than anything
 * drawn. Somebody watching a four-digit entry is left with eighty-one candidates instead of
 * the PIN.
 *
 * There is still no reveal button and no peek at the last character. The dots say how many
 * digits have been typed, which is a thing anybody in the room could count anyway.
 *
 * Digit keys on the remote are handled too — on this Philips they live under a modifier — and
 * they are the strongest input of the lot, since nothing at all appears on screen.
 */
class PinKeypad(context: Context, private val onSubmit: (String) -> Unit, private val onCancel: () -> Unit) :
    LinearLayout(context) {

    private val rows = listOf(
        KeypadRow("1", "2", "3"),
        KeypadRow("4", "5", "6"),
        KeypadRow("7", "8", "9"),
        // Zero on its own, as the platform draws it. Left and right on this row do nothing.
        KeypadRow("", "0", ""),
    )

    private val face = PinKeypadFace(context, rows)

    /** Starts on the middle row, as the platform's own screen does. */
    private var row = 1
    private var typed = ""

    init {
        orientation = VERTICAL
        gravity = Gravity.CENTER_HORIZONTAL
        // The keypad itself takes the focus and reads every key. Nothing inside it is
        // focusable, which is the point: with no focus to move, there is no highlight
        // wandering over the digits for somebody to read.
        isFocusable = true
        isFocusableInTouchMode = true
        // No box of its own: it is drawn on the same backdrop as the lock screen it replaces,
        // inside the same overscan margins.
        setPadding(
            context.dp(Spacing.SAFE_X),
            context.dp(Spacing.SAFE_Y),
            context.dp(Spacing.SAFE_X),
            context.dp(Spacing.SAFE_Y),
        )
        face.addTo(this)
        render()
    }

    /** Starts a step: a new question, nothing typed, nothing said about the last attempt. */
    fun prompt(text: String) {
        face.prompt.text = text
        face.say("", calm = true)
        row = 1
        clearEntry()
    }

    /**
     * Says what went wrong and clears the entry.
     *
     * Clearing is not politeness: leaving a rejected PIN in place invites pressing confirm
     * again, which spends another attempt on the same wrong answer.
     */
    fun message(text: String) {
        face.say(text, calm = text == context.getString(R.string.pin_checking))
        clearEntry()
    }

    fun focusKeypad() {
        requestFocus()
    }

    override fun dispatchKeyEvent(event: KeyEvent): Boolean {
        if (event.action != KeyEvent.ACTION_DOWN) return super.dispatchKeyEvent(event)

        val digit = event.keyCode - KeyEvent.KEYCODE_0
        if (digit in 0..LAST_DIGIT) {
            append(digit.toString())
            return true
        }

        return when (event.keyCode) {
            KeyEvent.KEYCODE_DPAD_UP -> moveRow(-1)
            KeyEvent.KEYCODE_DPAD_DOWN -> moveRow(1)
            KeyEvent.KEYCODE_DPAD_LEFT -> take(rows[row].left)
            KeyEvent.KEYCODE_DPAD_RIGHT -> take(rows[row].right)
            KeyEvent.KEYCODE_DPAD_CENTER, KeyEvent.KEYCODE_ENTER -> take(rows[row].centre)
            KeyEvent.KEYCODE_DEL -> {
                backspace()
                true
            }
            // Back is the delete key, as it is everywhere else on this platform: one digit at
            // a time, and once there is nothing left to delete it gives up on the keypad.
            KeyEvent.KEYCODE_BACK -> {
                if (typed.isEmpty()) onCancel() else backspace()
                true
            }

            else -> super.dispatchKeyEvent(event)
        }
    }

    private fun moveRow(by: Int): Boolean {
        // Wrapping, so the row a parent wants is never more than two presses away.
        row = (row + by + rows.size) % rows.size
        render()
        return true
    }

    private fun take(token: String): Boolean {
        if (token.isNotEmpty()) append(token)
        return true
    }

    private fun append(digit: String) {
        if (typed.length >= ParentPin.LENGTH) return
        typed += digit
        render()
        // The last digit submits itself, which is what the platform's own PIN screens do and
        // the reason this keypad needs no confirm button.
        if (typed.length == ParentPin.LENGTH) submit()
    }

    private fun backspace() {
        if (typed.isEmpty()) return
        typed = typed.dropLast(1)
        render()
    }

    private fun submit() {
        if (typed.length != ParentPin.LENGTH) return
        val entered = typed
        clearEntry()
        // Posted rather than called straight out: a correct PIN takes the lock down, and
        // removing a window from inside the key dispatch that asked for it is a good way to
        // lose the removal and leave a lock on screen that nothing thinks is there.
        post { onSubmit(entered) }
    }

    private fun clearEntry() {
        typed = ""
        render()
    }

    private fun render() {
        face.render(typed.length, row)
    }

    private companion object {
        const val LAST_DIGIT = 9
    }
}
