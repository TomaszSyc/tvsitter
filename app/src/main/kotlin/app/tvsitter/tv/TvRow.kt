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

/**
 * One pressable line of a list: what it is on the left, what it is set to on the right.
 *
 * A settings row used to be a button whose text read "Daily limit:  2 h 0 min", which is a label
 * and a value run together and read as one sentence. Apart, the eye goes down the left edge to
 * find the setting and across to find its state, the way every settings list on the platform reads.
 */
class TvRow(context: Context, onPress: () -> Unit) : LinearLayout(context) {

    private val label = context.tvText(TextRole.STRONG).apply { maxLines = 2 }
    private val value = context.tvText(TextRole.BODY).apply {
        maxLines = 1
        setPadding(context.dp(Spacing.XL), 0, 0, 0)
    }

    private var valueColour = Palette.SECONDARY

    init {
        orientation = HORIZONTAL
        gravity = Gravity.CENTER_VERTICAL
        isFocusable = true
        setOnClickListener { onPress() }
        val halo = context.dp(TvFocus.HALO_SPACE_DP)
        setPadding(
            halo + context.dp(Spacing.XL),
            halo + context.dp(PAD_Y_DP),
            halo + context.dp(Spacing.XL),
            halo + context.dp(PAD_Y_DP),
        )
        addView(label, LayoutParams(0, LayoutParams.WRAP_CONTENT, 1f))
        addView(value)
        TvFocus.follow(this, Rest.FILLED) { focused ->
            label.setTextColor(if (focused) Palette.ON_LIT else Palette.TEXT)
            value.setTextColor(if (focused) Palette.ON_LIT else valueColour)
        }
    }

    /** [state] is null for a row that does something rather than holding a setting. */
    fun show(name: String, state: String? = null, stateColour: Int = Palette.SECONDARY) {
        label.text = name
        value.text = state.orEmpty()
        value.visibility = if (state.isNullOrEmpty()) View.GONE else View.VISIBLE
        valueColour = stateColour
        if (!isFocused) value.setTextColor(stateColour)
    }

    private companion object {
        /** Makes the plate fifty-six tall around one line of body text. */
        const val PAD_Y_DP = 15
    }
}
