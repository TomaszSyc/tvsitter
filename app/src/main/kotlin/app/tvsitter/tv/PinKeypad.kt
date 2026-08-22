/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.tv

import android.content.Context
import android.graphics.Color
import android.util.TypedValue
import android.view.Gravity
import android.view.KeyEvent
import android.widget.Button
import android.widget.GridLayout
import android.widget.LinearLayout
import android.widget.TextView
import app.tvsitter.rules.ParentPin

/**
 * A keypad for typing a PIN with a remote control, which shows dots and never the digits.
 *
 * The masking is the reason this exists rather than a text field. A parent types this in front
 * of the person it is meant to keep out, on a screen the size of a wall: a PIN in clear text is
 * learned once, from across the room, and nobody finds out that it was. There is no reveal
 * button and no peek at the last character typed, because either one gives the whole code away
 * to somebody reading one digit at a time.
 *
 * Used by both places a PIN is typed — the lock screen and [PinActivity] — so that the two
 * cannot drift apart in what they show or in how they behave.
 *
 * Digit keys on the remote are handled as well as the on-screen grid. Some television remotes
 * have them and using them is much faster; that this also lets a child guess faster does not
 * matter, because what stops guessing is the lockout, not the effort of pressing buttons.
 */
class PinKeypad(context: Context, private val onSubmit: (String) -> Unit, private val onCancel: () -> Unit) :
    LinearLayout(context) {

    private val promptView = line(sizeSp = 26f, color = Color.WHITE)
    private val entryView = line(sizeSp = 34f, color = ACCENT).apply {
        letterSpacing = ENTRY_SPACING
        minLines = 1
    }
    private val messageView = line(sizeSp = 17f, color = WARNING).apply { minLines = 2 }

    private var typed = ""
    private var firstButton: Button? = null

    init {
        orientation = VERTICAL
        gravity = Gravity.CENTER_HORIZONTAL
        addView(promptView)
        addView(entryView)
        addView(buildGrid())
        addView(messageView)
    }

    /** Starts a step: a new question, nothing typed, nothing said about the last attempt. */
    fun prompt(text: String) {
        promptView.text = text
        messageView.text = ""
        clearEntry()
    }

    /**
     * Says what went wrong and clears the entry.
     *
     * Clearing is not politeness: leaving a rejected PIN in place invites pressing OK again,
     * which spends another attempt on the same wrong answer.
     */
    fun message(text: String) {
        messageView.text = text
        clearEntry()
    }

    fun focusKeypad() {
        firstButton?.requestFocus()
    }

    override fun dispatchKeyEvent(event: KeyEvent): Boolean {
        if (event.action != KeyEvent.ACTION_DOWN) return super.dispatchKeyEvent(event)

        val digit = event.keyCode - KeyEvent.KEYCODE_0
        return when {
            digit in 0..LAST_DIGIT -> {
                append(digit.toString())
                true
            }

            event.keyCode == KeyEvent.KEYCODE_DEL -> {
                backspace()
                true
            }

            // Back gets out of the keypad, one step at a time: it clears what was typed
            // before it gives up on the keypad altogether, so a mistyped digit does not mean
            // starting the whole thing again.
            event.keyCode == KeyEvent.KEYCODE_BACK -> {
                if (typed.isEmpty()) onCancel() else clearEntry()
                true
            }

            else -> super.dispatchKeyEvent(event)
        }
    }

    private fun buildGrid(): GridLayout {
        val grid = GridLayout(context).apply { columnCount = COLUMNS }
        for (digit in 1..LAST_DIGIT) {
            val label = digit.toString()
            grid.addView(keyButton(label) { append(label) })
        }
        grid.addView(keyButton(DELETE_LABEL) { backspace() })
        grid.addView(keyButton("0") { append("0") })
        grid.addView(keyButton(context.getString(R.string.pin_ok)) { submit() })
        return grid
    }

    private fun keyButton(label: String, onPress: () -> Unit): Button {
        val button = Button(context).apply {
            text = label
            isFocusable = true
            setTextSize(TypedValue.COMPLEX_UNIT_SP, KEY_TEXT_SP)
            setOnClickListener { onPress() }
            layoutParams = GridLayout.LayoutParams().apply {
                width = dp(KEY_WIDTH_DP)
                height = dp(KEY_HEIGHT_DP)
                setMargins(dp(KEY_MARGIN_DP), dp(KEY_MARGIN_DP), dp(KEY_MARGIN_DP), dp(KEY_MARGIN_DP))
            }
        }
        if (firstButton == null) firstButton = button
        return button
    }

    private fun append(digit: String) {
        // Silently ignored past the maximum rather than beeping about it: the length is the
        // parent's own choice and they know when they have finished.
        if (typed.length >= ParentPin.MAX_LENGTH) return
        typed += digit
        renderEntry()
    }

    private fun backspace() {
        if (typed.isEmpty()) return
        typed = typed.dropLast(1)
        renderEntry()
    }

    private fun submit() {
        if (typed.length < ParentPin.MIN_LENGTH) {
            message(context.getString(R.string.pin_length, ParentPin.MIN_LENGTH, ParentPin.MAX_LENGTH))
            return
        }
        val entered = typed
        clearEntry()
        // Posted rather than called straight out: a correct PIN takes the lock down, and
        // removing a window from inside the key dispatch that asked for it is a good way to
        // lose the removal and leave a lock on screen that nothing thinks is there.
        post { onSubmit(entered) }
    }

    private fun clearEntry() {
        typed = ""
        renderEntry()
    }

    private fun renderEntry() {
        entryView.text = MASK.repeat(typed.length)
    }

    private fun line(sizeSp: Float, color: Int) = TextView(context).apply {
        setTextColor(color)
        setTextSize(TypedValue.COMPLEX_UNIT_SP, sizeSp)
        gravity = Gravity.CENTER
        setPadding(0, 0, 0, dp(LINE_PADDING_DP))
    }

    private fun dp(value: Int): Int = (value * resources.displayMetrics.density).toInt()

    private companion object {
        const val LAST_DIGIT = 9
        const val MASK = "●"
        const val DELETE_LABEL = "⌫"
        const val COLUMNS = 3
        const val KEY_WIDTH_DP = 84
        const val KEY_HEIGHT_DP = 60
        const val KEY_MARGIN_DP = 6
        const val KEY_TEXT_SP = 22f
        const val LINE_PADDING_DP = 8
        const val ENTRY_SPACING = 0.4f
        const val ACCENT = 0xFF4CC2A5.toInt()
        const val WARNING = 0xFFF2B8B5.toInt()
    }
}
