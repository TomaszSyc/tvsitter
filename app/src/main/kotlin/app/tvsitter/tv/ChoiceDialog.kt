/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.tv

import android.app.Activity
import android.app.Dialog
import android.graphics.drawable.ColorDrawable
import android.view.Gravity
import android.view.ViewGroup
import android.view.Window
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.ScrollView

/** One thing a parent can pick, and what it means on the wire. */
data class Choice<T>(val label: String, val value: T)

/**
 * Picking one value from a few, with a D-pad.
 *
 * A list rather than a control that changes under the arrows, because the rest of this app is
 * buttons: press OK to open, press OK to choose, press back to leave. A row that quietly took
 * left and right would navigate unlike every other row on the screen, and the screen behaving
 * differently in one place is exactly what the shell was built to stop (#109).
 *
 * The current value is marked and takes the focus when the list opens, so a parent checking what
 * is set can press back without changing anything.
 */
object ChoiceDialog {

    fun <T> show(activity: Activity, title: String, choices: List<Choice<T>>, current: T?, onPick: (T) -> Unit) {
        val dialog = Dialog(activity)
        dialog.requestWindowFeature(Window.FEATURE_NO_TITLE)
        dialog.window?.setBackgroundDrawable(ColorDrawable(Palette.CLEAR))
        // The scrim is the window's dimming rather than a colour of our own, so it covers the
        // whole screen behind the card and not just the card's window.
        dialog.window?.setDimAmount(SCRIM)

        val list = LinearLayout(activity).apply {
            orientation = LinearLayout.VERTICAL
            TvFocus.letFocusOverflow(this)
        }
        var focusOn: TvRow? = null
        choices.forEach { choice ->
            val marked = choice.value == current
            val row = TvRow(activity) {
                dialog.dismiss()
                onPick(choice.value)
            }
            row.show(
                choice.label,
                if (marked) activity.getString(R.string.pick_current_mark) else null,
                Palette.ACCENT,
            )
            if (marked) focusOn = row
            list.addView(row, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, WRAP))
        }

        // Wrapped, because the platform gives a dialog window a minimum width of most of the
        // screen, and the card would be stretched to it. The window itself is clear.
        dialog.setContentView(
            FrameLayout(activity).apply {
                TvFocus.letFocusOverflow(this)
                addView(card(activity, title, list), FrameLayout.LayoutParams(WRAP, WRAP, Gravity.CENTER))
            },
        )
        dialog.window?.setGravity(Gravity.CENTER)
        dialog.show()
        // After show, because a view with no window attached cannot take focus yet.
        focusOn?.requestFocus()
    }

    private fun card(activity: Activity, title: String, list: LinearLayout) = LinearLayout(activity).apply {
        orientation = LinearLayout.VERTICAL
        background = activity.plate(Palette.SURFACE, Radius.XL, Palette.LINE)
        // The rows carry their own room for the focus ring, so the card's inset is that much
        // less at the sides and the plates still line up with the title.
        val halo = activity.dp(TvFocus.HALO_SPACE_DP)
        val side = activity.dp(Spacing.XXL) - halo
        setPadding(side, activity.dp(Spacing.XXL), side, activity.dp(Spacing.XL))
        TvFocus.letFocusOverflow(this)
        addView(
            activity.tvText(TextRole.HEADLINE).apply {
                text = title
                setPadding(halo, 0, halo, activity.dp(Spacing.L))
            },
        )
        addView(
            ScrollView(activity).apply {
                isFocusable = false
                TvFocus.letFocusOverflow(this)
                addView(list)
            },
            LinearLayout.LayoutParams(activity.dp(WIDTH_DP), WRAP),
        )
    }

    private const val SCRIM = 0.86f
    private const val WIDTH_DP = 440
    private const val WRAP = ViewGroup.LayoutParams.WRAP_CONTENT
}
