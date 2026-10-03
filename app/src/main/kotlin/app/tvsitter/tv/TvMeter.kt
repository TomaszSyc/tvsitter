/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.tv

import android.content.Context
import android.view.View
import android.widget.LinearLayout

/**
 * A bar on a track: how much of something, against how much there could be.
 *
 * The track is drawn as well as the bar, so a short bar reads as "a little of a lot" rather than
 * as a smudge. Split by layout weight rather than measured pixels, which keeps it right through a
 * resize without anybody having to remember to redraw it.
 */
class TvMeter(context: Context, heightDp: Int) : LinearLayout(context) {

    private val fill = View(context).apply { background = context.plate(Palette.ACCENT, heightDp / 2) }
    private val rest = View(context)

    init {
        orientation = HORIZONTAL
        background = context.plate(Palette.RAISED, heightDp / 2)
        minimumHeight = context.dp(heightDp)
        addView(fill, LayoutParams(0, LayoutParams.MATCH_PARENT, 0f))
        addView(rest, LayoutParams(0, LayoutParams.MATCH_PARENT, 1f))
    }

    fun show(part: Long, whole: Long) {
        val span = whole.coerceAtLeast(1)
        // So the shortest thing watched is still a bar rather than nothing at all.
        val shown = if (part > 0) part.coerceIn((span * SHORTEST).toLong(), span) else 0L
        (fill.layoutParams as LayoutParams).weight = shown.toFloat()
        (rest.layoutParams as LayoutParams).weight = (span - shown).toFloat()
        requestLayout()
    }

    private companion object {
        const val SHORTEST = 0.03
    }
}
