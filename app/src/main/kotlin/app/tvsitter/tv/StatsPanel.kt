/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.tv

import android.content.Context
import android.graphics.drawable.GradientDrawable
import android.view.Gravity
import android.view.View
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView

/**
 * What was actually watched, at the set.
 *
 * Everything here is already counted and already published — the per-app split since M5, the
 * closed day since #78 — and none of it could be seen on the television itself, which is the one
 * place somebody stands when Home Assistant is not to hand (#111).
 *
 * A list reads down and each app's own detail reads across: the axis the platform's guidance asks
 * for, and the axis a bar chart is read in anyway. The bar is proportional to the longest thing
 * watched rather than to the day's limit, because the question this screen answers is what he is
 * watching, and against a limit the interesting rows are all short.
 */
class StatsPanel(private val context: Context) {

    private val todayList = LinearLayout(context).apply { orientation = LinearLayout.VERTICAL }
    private val yesterdayLine = text(TvStyle.BODY_SP, TvStyle.TEXT)
    private val yesterdayList = LinearLayout(context).apply { orientation = LinearLayout.VERTICAL }

    val view: View = ScrollView(context).apply {
        isFillViewport = true
        addView(
            LinearLayout(context).apply {
                orientation = LinearLayout.VERTICAL
                setPadding(TvStyle.OVERSCAN_PX, TvStyle.OVERSCAN_PX, TvStyle.OVERSCAN_PX, TvStyle.OVERSCAN_PX)
                addView(heading(R.string.stats_today))
                addView(todayList)
                addView(heading(R.string.stats_yesterday))
                addView(yesterdayLine)
                addView(yesterdayList)
                addView(
                    text(TvStyle.SMALL_SP, TvStyle.MUTED).apply {
                        setText(R.string.stats_week_note)
                        setPadding(0, TvStyle.OVERSCAN_PX / 2, 0, 0)
                    },
                )
            },
        )
    }

    fun refresh() {
        val service = EnforcerService.instance
        fill(todayList, service?.perAppToday.orEmpty(), service, R.string.stats_nothing)

        val closed = service?.yesterday
        yesterdayLine.text = closed?.let {
            context.getString(
                R.string.stats_yesterday_line,
                TvStyle.length(context, it.usedSeconds),
                it.limitSeconds?.let { limit -> TvStyle.length(context, limit) }
                    ?: context.getString(R.string.set_no_limit),
                TvStyle.length(context, it.grantedSeconds),
                it.lockCount,
            )
        } ?: context.getString(R.string.stats_no_yesterday)

        // The names come with the closed day rather than from the resolver: an app uninstalled
        // overnight still has to be called what it was called when it was watched.
        fill(yesterdayList, closed?.perApp.orEmpty(), service, null, closed?.perAppNames.orEmpty())
    }

    private fun fill(
        into: LinearLayout,
        perApp: Map<String, Int>,
        service: EnforcerService?,
        emptyRes: Int?,
        names: Map<String, String> = emptyMap(),
    ) {
        into.removeAllViews()
        if (perApp.isEmpty()) {
            emptyRes?.let { into.addView(text(TvStyle.BODY_SP, TvStyle.MUTED).apply { setText(it) }) }
            return
        }
        // Longest first: the question is what he is watching, and the answer is at the top.
        val ordered = perApp.entries.sortedByDescending { it.value }.take(MOST)
        val longest = ordered.first().value.coerceAtLeast(1)
        ordered.forEach { (pkg, seconds) ->
            val name = names[pkg] ?: service?.labels?.labelOf(pkg) ?: pkg
            into.addView(row(name, seconds, longest))
        }
    }

    private fun row(name: String, seconds: Int, longest: Int) = LinearLayout(context).apply {
        orientation = LinearLayout.HORIZONTAL
        gravity = Gravity.CENTER_VERTICAL
        setPadding(0, TvStyle.GAP_PX / 2, 0, TvStyle.GAP_PX / 2)
        addView(
            text(TvStyle.BODY_SP, TvStyle.TEXT).apply {
                text = name
                width = NAME_WIDTH_PX
                maxLines = 1
                ellipsize = android.text.TextUtils.TruncateAt.END
            },
        )
        addView(
            View(context).apply {
                background = GradientDrawable().apply {
                    cornerRadius = BAR_CORNER_PX
                    setColor(TvStyle.ACCENT)
                }
            },
            LinearLayout.LayoutParams(
                (BAR_WIDTH_PX.toLong() * seconds / longest).toInt().coerceAtLeast(BAR_MINIMUM_PX),
                BAR_HEIGHT_PX,
            ),
        )
        addView(
            text(TvStyle.BODY_SP, TvStyle.MUTED).apply {
                text = TvStyle.length(context, seconds)
                setPadding(TvStyle.GAP_PX, 0, 0, 0)
            },
        )
    }

    private fun heading(labelRes: Int) = text(TvStyle.HEADING_SP, TvStyle.TEXT).apply {
        setText(labelRes)
        setPadding(0, TvStyle.OVERSCAN_PX / 2, 0, TvStyle.GAP_PX / 2)
    }

    private fun text(sizeSp: Float, colour: Int) = TextView(context).apply {
        setTextColor(colour)
        setTextSize(android.util.TypedValue.COMPLEX_UNIT_SP, sizeSp)
    }

    private companion object {
        /** Enough to answer the question. A television with thirty apps does not need thirty rows. */
        const val MOST = 6
        const val NAME_WIDTH_PX = 460
        const val BAR_WIDTH_PX = 520
        const val BAR_HEIGHT_PX = 22

        /** So the shortest thing watched is still a bar rather than nothing at all. */
        const val BAR_MINIMUM_PX = 12
        const val BAR_CORNER_PX = 11f
    }
}
