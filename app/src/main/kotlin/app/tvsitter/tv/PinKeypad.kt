/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.tv

import android.content.Context
import android.graphics.Color
import android.graphics.drawable.GradientDrawable
import android.util.TypedValue
import android.view.Gravity
import android.view.KeyEvent
import android.widget.LinearLayout
import android.widget.TextView
import app.tvsitter.rules.ParentPin

/**
 * Typing a PIN with a remote control, in the shape Google TV uses for its own PIN.
 *
 * Up and down move between rows of three digits; left, centre and right pick one of the three
 * in the row showing. A map of the rows sits underneath so the layout can be learned rather
 * than hunted for. Two presses per digit, usually.
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

    /** Three tokens, laid out as left, centre and right, matching the D-pad's own geometry. */
    private data class Row(val left: String, val centre: String, val right: String)

    private val rows = listOf(
        Row("1", "2", "3"),
        Row("4", "5", "6"),
        Row("7", "8", "9"),
        // Zero on its own, as the platform draws it. Left and right on this row do nothing.
        Row("", "0", ""),
    )

    private val promptView = context.pinLine(PROMPT_SP, Color.WHITE)
    private val progressView = context.pinLine(PROGRESS_SP, ACCENT).apply {
        letterSpacing = PROGRESS_SPACING
    }
    private val messageView = context.pinLine(MESSAGE_SP, WARNING).apply { minLines = 2 }

    private val leftView = context.pinLine(WHEEL_SIDE_SP, MUTED, WHEEL_PADDING_DP)
    private val centreView = context.pinLine(WHEEL_CENTRE_SP, Color.WHITE, WHEEL_PADDING_DP).apply {
        background = outline(oval = true, radiusDp = 0, context = context)
        width = context.px(RING_DP)
        height = context.px(RING_DP)
    }
    private val rightView = context.pinLine(WHEEL_SIDE_SP, MUTED, WHEEL_PADDING_DP)
    private val mapViews = rows.map { context.pinLine(MAP_SP, MUTED) }

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

        addView(promptView)
        addView(progressView)
        addView(buildWheel())
        addView(buildMap())
        addView(messageView)
        render()
    }

    /** Starts a step: a new question, nothing typed, nothing said about the last attempt. */
    fun prompt(text: String) {
        promptView.text = text
        messageView.text = ""
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
        messageView.text = text
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
        val filled = MASK.repeat(typed.length)
        val remaining = EMPTY.repeat((ParentPin.LENGTH - typed.length).coerceAtLeast(0))
        progressView.text = filled + remaining

        val showing = rows[row]
        leftView.text = showing.left
        centreView.text = showing.centre
        rightView.text = showing.right

        mapViews.forEachIndexed { index, view ->
            val line = rows[index]
            view.text = listOf(line.left, line.centre, line.right)
                .filter { it.isNotEmpty() }
                .joinToString(separator = "   ")
            view.setTextColor(if (index == row) Color.WHITE else MUTED)
            view.background =
                if (index == row) outline(oval = false, radiusDp = PILL_RADIUS_DP, context = context) else null
        }
    }

    private fun buildWheel() = LinearLayout(context).apply {
        orientation = VERTICAL
        gravity = Gravity.CENTER_HORIZONTAL
        addView(context.pinLine(ARROW_SP, MUTED).apply { text = "▲" })
        addView(
            LinearLayout(context).apply {
                orientation = HORIZONTAL
                // Both axes. A vertical LinearLayout hands its children the full width, so
                // CENTER_VERTICAL alone left the three digits packed against the left edge
                // while the dots, arrows and map above and below them sat centred.
                gravity = Gravity.CENTER
                addView(leftView)
                addView(centreView)
                addView(rightView)
            },
        )
        addView(context.pinLine(ARROW_SP, MUTED).apply { text = "▼" })
    }

    private fun buildMap() = LinearLayout(context).apply {
        orientation = VERTICAL
        gravity = Gravity.CENTER_HORIZONTAL
        setPadding(0, context.px(GAP_DP), 0, 0)
        mapViews.forEach { addView(it) }
    }

    private companion object {
        const val LAST_DIGIT = 9
        const val MASK = "●"
        const val EMPTY = "○"

        const val PROMPT_SP = 26f
        const val PROGRESS_SP = 30f
        const val MESSAGE_SP = 17f
        const val MAP_SP = 18f
        const val ARROW_SP = 20f
        const val WHEEL_SIDE_SP = 30f
        const val WHEEL_CENTRE_SP = 34f
        const val PROGRESS_SPACING = 0.4f

        const val RING_DP = 68
        const val PILL_RADIUS_DP = 14
        const val WHEEL_PADDING_DP = 18
        const val GAP_DP = 12

        const val ACCENT = 0xFF4CC2A5.toInt()
        const val WARNING = 0xFFF2B8B5.toInt()
        const val MUTED = 0xFFB9C6D2.toInt()
    }
}

private fun Context.px(dp: Int): Int = (dp * resources.displayMetrics.density).toInt()

private fun Context.pinLine(sizeSp: Float, color: Int, padSidesDp: Int = LINE_PADDING_DP) = TextView(this).apply {
    setTextColor(color)
    setTextSize(TypedValue.COMPLEX_UNIT_SP, sizeSp)
    gravity = Gravity.CENTER
    setPadding(px(padSidesDp), px(LINE_PADDING_DP), px(padSidesDp), px(LINE_PADDING_DP))
}

private fun outline(oval: Boolean, radiusDp: Int, context: Context) = GradientDrawable().apply {
    shape = if (oval) GradientDrawable.OVAL else GradientDrawable.RECTANGLE
    if (!oval) cornerRadius = context.px(radiusDp).toFloat()
    setStroke(context.px(STROKE_DP), OUTLINE_COLOR)
}

private const val LINE_PADDING_DP = 4
private const val STROKE_DP = 2
private const val OUTLINE_COLOR = 0xFFB9C6D2.toInt()
