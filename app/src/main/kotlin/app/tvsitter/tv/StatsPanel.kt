/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.tv

import android.content.Context
import android.view.View
import android.widget.LinearLayout
import android.widget.TextView

/**
 * What was actually watched, at the set.
 *
 * Everything here is already counted and already published — the per-app split since M5, the
 * closed day since #78 — and none of it could be seen on the television itself, which is the one
 * place somebody stands when Home Assistant is not to hand (#111).
 */
class StatsPanel(private val context: Context) {

    private val todayList = LinearLayout(context).apply { orientation = LinearLayout.VERTICAL }
    private val yesterday = text(TvStyle.BODY_SP, TvStyle.MUTED)

    val view: View = LinearLayout(context).apply {
        orientation = LinearLayout.VERTICAL
        setPadding(TvStyle.OVERSCAN_PX, TvStyle.OVERSCAN_PX, TvStyle.OVERSCAN_PX, TvStyle.OVERSCAN_PX)
        addView(text(TvStyle.HEADING_SP, TvStyle.TEXT).apply { setText(R.string.stats_today) })
        addView(todayList)
        addView(
            text(TvStyle.SMALL_SP, TvStyle.MUTED).apply {
                setText(R.string.stats_yesterday)
                setPadding(0, TvStyle.OVERSCAN_PX, 0, 0)
            },
        )
        addView(yesterday)
    }

    fun refresh() {
        todayList.removeAllViews()
        val service = EnforcerService.instance
        val perApp = service?.perAppToday.orEmpty()
        if (perApp.isEmpty()) {
            todayList.addView(text(TvStyle.BODY_SP, TvStyle.MUTED).apply { setText(R.string.stats_nothing) })
        } else {
            // Longest first: the question is what he is watching, and the answer is at the top.
            perApp.entries.sortedByDescending { it.value }.take(MOST).forEach { (pkg, seconds) ->
                todayList.addView(row(service?.labels?.labelOf(pkg) ?: pkg, seconds))
            }
        }
        yesterday.text = service?.yesterday ?: context.getString(R.string.stats_no_yesterday)
    }

    private fun row(name: String, seconds: Int) = LinearLayout(context).apply {
        orientation = LinearLayout.HORIZONTAL
        setPadding(0, TvStyle.GAP_PX / 2, 0, TvStyle.GAP_PX / 2)
        addView(
            text(TvStyle.BODY_SP, TvStyle.TEXT).apply {
                text = name
                width = NAME_WIDTH_PX
            },
        )
        addView(text(TvStyle.BODY_SP, TvStyle.ACCENT).apply { text = TvStyle.length(context, seconds) })
    }

    private fun text(sizeSp: Float, colour: Int) = TextView(context).apply {
        setTextColor(colour)
        setTextSize(android.util.TypedValue.COMPLEX_UNIT_SP, sizeSp)
    }

    private companion object {
        /** Enough to answer the question. A television with thirty apps does not need thirty rows. */
        const val MOST = 8
        const val NAME_WIDTH_PX = 520
    }
}
