/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.tv

import android.content.Context
import android.view.Gravity
import android.view.View
import android.widget.LinearLayout
import android.widget.TextView

/** Three digits, laid out as left, centre and right, matching the D-pad's own geometry. */
internal data class KeypadRow(val left: String, val centre: String, val right: String) {
    val digits: List<String> get() = listOf(left, centre, right).filter { it.isNotEmpty() }
}

/**
 * What [PinKeypad] draws, kept apart from what it does with the keys.
 *
 * Drawn straight onto the backdrop the way the lock screen is, rather than in a box: the question
 * in the lock screen's title, a dot per digit, and the row in play as three large digits with the
 * key that takes each one written under it. The rows either side of it sit above and below,
 * faded, so up and down explain themselves without a map.
 *
 * Nothing in here is focusable and nothing changes with the digit that was taken, only with the
 * row. That is the property the keypad exists for — see [PinKeypad] — and it is a property of the
 * drawing as much as of the input.
 */
internal class PinKeypadFace(private val context: Context, private val rows: List<KeypadRow>) {

    val prompt: TextView = context.tvText(TextRole.DISPLAY).apply { gravity = Gravity.CENTER }
    private val message = context.tvText(TextRole.LEAD, Palette.ERROR).apply {
        gravity = Gravity.CENTER
        minLines = 1
    }

    private val dots = List(PIN_DIGITS) { View(context) }
    private val above = neighbour()
    private val below = neighbour()
    private val slots = List(SLOTS) { index -> slot(centre = index == 1) }
    private val keys = listOf("←", context.getString(R.string.pin_key_ok), "→").map { key ->
        context.tvText(TextRole.LABEL).apply {
            text = key
            gravity = Gravity.CENTER
        }
    }

    /** Everything, top to bottom, centred on the backdrop. */
    fun addTo(column: LinearLayout) {
        column.addView(prompt)
        column.addView(dotRow(), gap(Spacing.XL))
        // Unequal gaps for equal spacing: the key hints hang under the row in play, so the gap
        // above it is the gap below it plus the hints, and the three rows' centres are even.
        column.addView(columns(above), gap(Spacing.XXL))
        column.addView(wheel(), gap(ROW_GAP_ABOVE_DP))
        column.addView(columns(below), gap(Spacing.L))
        column.addView(message, gap(Spacing.XL))
    }

    fun render(typed: Int, row: Int) {
        dots.forEachIndexed { index, dot ->
            dot.background = if (index < typed) {
                context.dot(Palette.ACCENT, DOT_DP)
            } else {
                context.dot(Palette.TERTIARY, DOT_DP, filled = false)
            }
        }
        val showing = rows[row]
        listOf(showing.left, showing.centre, showing.right).forEachIndexed { index, digit ->
            slots[index].text = digit
            // The zero row has nothing at the sides, and a key label over nothing is a promise.
            keys[index].visibility = if (digit.isEmpty()) View.INVISIBLE else View.VISIBLE
        }
        show(above, rows[(row - 1 + rows.size) % rows.size])
        show(below, rows[(row + 1) % rows.size])
    }

    /** "Checking…" is news rather than a fault, so it is not written in the colour of one. */
    fun say(text: String, calm: Boolean) {
        message.text = text
        message.setTextColor(if (calm) Palette.SECONDARY else Palette.ERROR)
    }

    private fun dotRow() = LinearLayout(context).apply {
        orientation = LinearLayout.HORIZONTAL
        gravity = Gravity.CENTER
        dots.forEachIndexed { index, dot ->
            addView(
                dot,
                LinearLayout.LayoutParams(context.dp(DOT_DP), context.dp(DOT_DP)).apply {
                    if (index > 0) marginStart = context.dp(DOT_GAP_DP)
                },
            )
        }
    }

    /** Three columns of the same width, each a digit with the key that takes it underneath. */
    private fun wheel() = LinearLayout(context).apply {
        orientation = LinearLayout.HORIZONTAL
        gravity = Gravity.CENTER
        slots.forEachIndexed { index, digit ->
            addView(
                LinearLayout(context).apply {
                    orientation = LinearLayout.VERTICAL
                    gravity = Gravity.CENTER_HORIZONTAL
                    addView(digit, LinearLayout.LayoutParams(context.dp(RING_DP), context.dp(RING_DP)))
                    addView(
                        keys[index],
                        // Tight under its digit, so the pair reads as one thing.
                        LinearLayout.LayoutParams(WRAP, WRAP).apply {
                            topMargin = context.dp(Spacing.XS)
                        },
                    )
                },
                LinearLayout.LayoutParams(context.dp(SLOT_WIDTH_DP), WRAP),
            )
        }
    }

    /**
     * The centre digit is ringed in mint because it is the one OK takes. The ring is always there
     * and never moves: it marks a key on the remote, not a choice somebody made.
     */
    private fun slot(centre: Boolean) = context.tvText(
        if (centre) TextRole.HEADLINE else TextRole.LEAD,
        if (centre) Palette.TEXT else Palette.SECONDARY,
    ).apply {
        gravity = Gravity.CENTER
        textSize = if (centre) CENTRE_SP else SIDE_SP
        setLineSpacing(0f, 1f)
        if (centre) {
            background = context.dot(Palette.ACCENT, RING_DP, filled = false)
        }
    }

    /**
     * A row either side, on the same three columns as the row in play so 4 sits under 1 and up and
     * down read as moving the whole keypad. Quieter by size and colour, and still clear of AA.
     */
    private fun neighbour() = List(SLOTS) {
        context.tvText(TextRole.LEAD, Palette.TERTIARY).apply {
            gravity = Gravity.CENTER
            textSize = NEIGHBOUR_SP
        }
    }

    private fun columns(cells: List<TextView>) = LinearLayout(context).apply {
        orientation = LinearLayout.HORIZONTAL
        gravity = Gravity.CENTER
        cells.forEach { addView(it, LinearLayout.LayoutParams(context.dp(SLOT_WIDTH_DP), WRAP)) }
    }

    private fun show(cells: List<TextView>, row: KeypadRow) {
        listOf(row.left, row.centre, row.right).forEachIndexed { index, digit -> cells[index].text = digit }
    }

    private fun gap(topDp: Int) = LinearLayout.LayoutParams(WRAP, WRAP).apply { topMargin = context.dp(topDp) }

    private companion object {
        const val WRAP = LinearLayout.LayoutParams.WRAP_CONTENT
        const val PIN_DIGITS = 4
        const val SLOTS = 3

        const val DOT_DP = 18
        const val DOT_GAP_DP = 22
        const val RING_DP = 92
        const val SLOT_WIDTH_DP = 128
        const val CENTRE_SP = 54f
        const val SIDE_SP = 40f
        const val NEIGHBOUR_SP = 26f

        /** The gap below the row in play plus the height of its key hints. */
        const val ROW_GAP_ABOVE_DP = 40
    }
}
