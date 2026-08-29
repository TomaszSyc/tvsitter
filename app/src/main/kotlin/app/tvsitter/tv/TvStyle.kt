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
import android.view.ViewGroup
import android.widget.Button

/**
 * What every screen here looks like, in one place.
 *
 * It lives on its own because the alternative was measured by somebody using the thing: the lock
 * screen was given a type scale and a focus treatment, the setup screen kept the platform's grey
 * slabs in capitals, and two screens of the same application looked like two applications.
 *
 * A television is read from three metres, navigated with four arrows, usually at night.
 */
object TvStyle {
    const val BACKDROP = 0xFF0B1017.toInt()
    const val SURFACE = 0xFF141F2B.toInt()
    const val ACCENT = 0xFF5BE1BE.toInt()
    const val TEXT = 0xFFF2F6F9.toInt()
    const val MUTED = 0xFF8FA3B3.toInt()
    const val WARN = 0xFFFFC46B.toInt()

    /** The rail's current destination when the rail does not have the focus. */
    const val ACTIVE = 0xFF20303F.toInt()

    const val TITLE_SP = 44f
    const val HEADING_SP = 30f
    const val BODY_SP = 20f
    const val SMALL_SP = 15f
    const val NUMBER_SP = 40f

    const val OVERSCAN_PX = 64
    const val GAP_PX = 20

    private const val SECONDS_PER_MINUTE = 60
    private const val MINUTES_PER_HOUR = 60

    private const val BUTTON_SP = 20f
    private const val BUTTON_PADDING_PX = 56
    private const val BUTTON_COLOR = 0xFF1C2733.toInt()
    private const val BUTTON_FOCUS_COLOR = 0xFFE8EEF4.toInt()

    /**
     * A pill at rest, squarer when focused, which is shape-as-state the way the platform's own
     * components do it now.
     *
     * It first looked wrong for a different reason: the scale-up was being clipped by the
     * container's padding, so the focused button lost its left corner and read as cut off rather
     * than as selected. That was the bug — see [letFocusOverflow] — and the shape change is not.
     */
    private const val RESTING_RADIUS_PX = 48f
    private const val FOCUS_RADIUS_PX = 20f
    private const val FOCUS_SCALE = 1.06f
    private const val FOCUS_MS = 120L

    /**
     * A length somebody can read without decoding it.
     *
     * "3:55" was shipped and is a riddle: hours and minutes, or minutes and seconds? A number on
     * a television says what it is, or it is not a number. So the unit is always on it.
     */
    fun length(context: Context, seconds: Int?): String {
        val total = ((seconds ?: 0) + SECONDS_PER_MINUTE - 1) / SECONDS_PER_MINUTE
        if (total < MINUTES_PER_HOUR) return context.getString(R.string.dur_minutes, total)
        return context.getString(
            R.string.dur_hours,
            total / MINUTES_PER_HOUR,
            total % MINUTES_PER_HOUR,
        )
    }

    /**
     * Makes a button readable and, more importantly, obviously selected from a sofa.
     *
     * With a D-pad the focused element is the cursor: if you cannot tell which one it is from
     * across the room, the screen is broken however pretty it is. Three things change at once —
     * fill, corner radius and size — because one signal does not survive a washed-out panel in a
     * bright room, and shape-as-state is what the platform's own components do now.
     *
     * Shouting is off. A child reading block capitals is being told off by a machine.
     */
    fun dress(button: Button) {
        button.isAllCaps = false
        button.setTextSize(TypedValue.COMPLEX_UNIT_SP, BUTTON_SP)
        button.setPadding(
            BUTTON_PADDING_PX,
            BUTTON_PADDING_PX / 2,
            BUTTON_PADDING_PX,
            BUTTON_PADDING_PX / 2,
        )
        paint(button, focused = false)
        button.setOnFocusChangeListener { view, focused -> paint(view as Button, focused) }
    }

    /**
     * Lets a focused child grow past its parent's edges.
     *
     * Without this the scale-up is clipped by the container's padding, and a button at the left
     * margin loses the very corner that shows it is a button — measured on the setup screen,
     * where the focused one looked cut off down its left side.
     */
    fun letFocusOverflow(group: ViewGroup) {
        group.clipChildren = false
        group.clipToPadding = false
    }

    private fun paint(button: Button, focused: Boolean) {
        button.background = GradientDrawable().apply {
            cornerRadius = if (focused) FOCUS_RADIUS_PX else RESTING_RADIUS_PX
            setColor(if (focused) BUTTON_FOCUS_COLOR else BUTTON_COLOR)
        }
        button.setTextColor(if (focused) BACKDROP else Color.WHITE)
        button.animate()
            .scaleX(if (focused) FOCUS_SCALE else 1f)
            .scaleY(if (focused) FOCUS_SCALE else 1f)
            .setDuration(FOCUS_MS)
            .start()
    }
}
