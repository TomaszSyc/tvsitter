/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.tv

import android.app.Activity
import android.app.Dialog
import android.graphics.drawable.ColorDrawable
import android.graphics.drawable.GradientDrawable
import android.util.TypedValue
import android.view.Gravity
import android.view.ViewGroup
import android.view.Window
import android.widget.Button
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView

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
        dialog.window?.setBackgroundDrawable(ColorDrawable(SCRIM))

        val list = LinearLayout(activity).apply { orientation = LinearLayout.VERTICAL }
        var focusOn: Button? = null
        choices.forEach { choice ->
            val marked = choice.value == current
            val button = Button(activity).apply {
                text = if (marked) activity.getString(R.string.pick_current, choice.label) else choice.label
                setOnClickListener {
                    dialog.dismiss()
                    onPick(choice.value)
                }
            }
            TvStyle.dress(button)
            if (marked) focusOn = button
            list.addView(
                button,
                LinearLayout.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT,
                    ViewGroup.LayoutParams.WRAP_CONTENT,
                ).apply { setMargins(TvStyle.GAP_PX, TvStyle.GAP_PX / 2, TvStyle.GAP_PX, TvStyle.GAP_PX / 2) },
            )
        }

        dialog.setContentView(
            LinearLayout(activity).apply {
                orientation = LinearLayout.VERTICAL
                background = GradientDrawable().apply {
                    cornerRadius = CORNER_PX
                    setColor(TvStyle.SURFACE)
                }
                setPadding(TvStyle.OVERSCAN_PX, TvStyle.GAP_PX * 2, TvStyle.OVERSCAN_PX, TvStyle.GAP_PX * 2)
                TvStyle.letFocusOverflow(this)
                addView(
                    TextView(activity).apply {
                        text = title
                        setTextColor(TvStyle.TEXT)
                        setTextSize(TypedValue.COMPLEX_UNIT_SP, TvStyle.HEADING_SP)
                        setPadding(TvStyle.GAP_PX, 0, 0, TvStyle.GAP_PX)
                    },
                )
                addView(
                    ScrollView(activity).apply {
                        isFocusable = false
                        TvStyle.letFocusOverflow(this)
                        addView(list)
                    },
                    LinearLayout.LayoutParams(WIDTH_PX, ViewGroup.LayoutParams.WRAP_CONTENT),
                )
            },
        )
        dialog.window?.setGravity(Gravity.CENTER)
        dialog.show()
        // After show, because a view with no window attached cannot take focus yet.
        focusOn?.requestFocus()
    }

    private const val SCRIM = 0xCC05080C.toInt()
    private const val CORNER_PX = 32f
    private const val WIDTH_PX = 760
}
