/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.tv

import android.content.Context
import android.util.TypedValue
import android.widget.TextView
import androidx.core.widget.TextViewCompat

/**
 * The colours every screen is painted with.
 *
 * A room at night rather than a void: the backdrop is a blue-black, the surfaces step up from it
 * in small, even increments, and there is one accent — the mint from the app's own mark — so that
 * anything mint means either "this is the cursor" or "this is the number that matters".
 *
 * Every text colour clears WCAG AA on every surface it is used on, and the quietest of them,
 * [TERTIARY] on [RAISED], still clears 5:1. A television is read from three metres on a panel
 * that may be washing everything out, so AA is the floor here rather than the goal.
 */
object Palette {
    const val INK = 0xFF0B1117.toInt()

    /** The faint glow at the top of a full screen. Never behind text that has to be read. */
    const val DUSK = 0xFF11272D.toInt()
    const val SURFACE = 0xFF141D26.toInt()
    const val RAISED = 0xFF1C2732.toInt()

    /** Hairlines that separate without being read as a control. */
    const val LINE = 0xFF2C3A47.toInt()

    /** The outline of a control with no fill, which has to clear 3:1 to be seen as one. */
    const val EDGE = 0xFF5A6B7A.toInt()

    const val TEXT = 0xFFEEF3F6.toInt()
    const val SECONDARY = 0xFFB4C1CC.toInt()
    const val TERTIARY = 0xFF8798A7.toInt()

    const val ACCENT = 0xFF5BE1BE.toInt()
    const val ACCENT_DIM = 0xFF173A35.toInt()
    const val WARN = 0xFFF6C467.toInt()
    const val WARN_DIM = 0xFF2E2715.toInt()

    /** Rose rather than red: a wrong PIN is a fact to read, not an alarm. */
    const val ERROR = 0xFFF4A9A3.toInt()

    /** The focused control. Near white, so it is the brightest thing on any screen. */
    const val LIT = 0xFFF2F6F9.toInt()
    const val ON_LIT = INK

    const val CLEAR = 0x00000000
}

/**
 * Text sizes for three metres, in sp.
 *
 * Measured against a 1080p panel at xhdpi, where one sp is two pixels: the smallest size here is
 * thirty pixels tall, which is about where a word stops being read and starts being decoded from a
 * sofa. Nothing on any screen goes below [LABEL].
 */
object TypeScale {
    const val DISPLAY = 44f
    const val HEADLINE = 28f
    const val LEAD = 24f
    const val TITLE = 22f
    const val BUTTON = 20f
    const val BODY = 18f
    const val LABEL = 15f
    const val NUMBER = 44f
    const val CODE = 64f
}

/** One spacing scale in dp, so gaps line up across screens rather than across one screen. */
object Spacing {
    const val XS = 4
    const val S = 8
    const val M = 12
    const val L = 16
    const val XL = 24
    const val XXL = 32
    const val XXXL = 48

    /**
     * The platform's own overscan margins for a ten-foot screen. Some sets still crop the edges,
     * and the one thing that must not be cropped is the cursor.
     */
    const val SAFE_X = 48
    const val SAFE_Y = 32
}

/** Corner radii in dp. One per size of thing, rather than one per screen. */
object Radius {
    const val S = 12
    const val M = 16
    const val L = 24
    const val XL = 28
}

fun Context.dp(value: Int): Int = (value * resources.displayMetrics.density).toInt()

fun Context.dp(value: Float): Float = value * resources.displayMetrics.density

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
    private const val SECONDS_PER_MINUTE = 60
    private const val MINUTES_PER_HOUR = 60

    /** Below this it stops being the headline number on the screen. */
    private const val SMALLEST_NUMBER_SP = 22
    private const val AUTOSIZE_STEP_SP = 1

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
     * Lets a big number shrink rather than wrap.
     *
     * The three figures on Today share the width equally and none of them has a fixed length:
     * "4 h 17 min" is nearly twice "45 min" and half again on a set showing hours in Polish.
     * At a fixed size the longest one wraps onto a second line and the labels beside the three
     * stop lining up, which is worse than a slightly smaller number.
     */
    fun fitNumber(view: TextView) {
        view.maxLines = 1
        TextViewCompat.setAutoSizeTextTypeUniformWithConfiguration(
            view,
            SMALLEST_NUMBER_SP,
            TypeScale.NUMBER.toInt(),
            AUTOSIZE_STEP_SP,
            TypedValue.COMPLEX_UNIT_SP,
        )
    }
}
