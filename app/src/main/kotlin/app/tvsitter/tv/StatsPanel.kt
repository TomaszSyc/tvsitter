/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.tv

import android.content.Context
import android.text.TextUtils
import android.view.Gravity
import android.view.View
import android.widget.LinearLayout
import android.widget.ScrollView

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
    private val yesterdayLine = context.tvText(TextRole.BODY)

    // Hidden until there is a day behind it. A label over nothing is the empty frame #111
    // asked for instead of, and it read as a list that had failed to load.
    private val yesterdayLabel = context.tvText(TextRole.LABEL).apply {
        setText(R.string.stats_yesterday_apps)
        setPadding(0, context.dp(Spacing.L), 0, context.dp(Spacing.XS))
    }
    private val yesterdayList = LinearLayout(context).apply { orientation = LinearLayout.VERTICAL }

    val view: View = ScrollView(context).apply {
        isFillViewport = true
        addView(
            LinearLayout(context).apply {
                orientation = LinearLayout.VERTICAL
                setPadding(
                    context.dp(Spacing.SAFE_X),
                    context.dp(Spacing.SAFE_Y),
                    context.dp(Spacing.SAFE_X),
                    context.dp(Spacing.SAFE_Y),
                )
                addView(heading(R.string.stats_today, first = true))
                addView(todayList)
                addView(heading(R.string.stats_yesterday, first = false))
                addView(yesterdayLine)
                addView(yesterdayLabel)
                addView(yesterdayList)
                addView(
                    context.tvText(TextRole.LABEL).apply {
                        setText(R.string.stats_week_note)
                        setPadding(0, context.dp(Spacing.XXL), 0, 0)
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
        val split = closed?.perApp.orEmpty()
        yesterdayLabel.visibility = if (split.isEmpty()) View.GONE else View.VISIBLE
        fill(yesterdayList, split, service, null, closed?.perAppNames.orEmpty())
    }

    private fun fill(
        into: LinearLayout,
        perApp: Map<String, Int>,
        service: EnforcerService?,
        emptyRes: Int?,
        names: Map<String, String> = emptyMap(),
    ) {
        into.removeAllViews()
        // The launcher and the system are the set idling, not something anybody watched.
        val shown = perApp - service?.exemptApps.orEmpty()
        if (shown.isEmpty()) {
            emptyRes?.let { into.addView(context.tvText(TextRole.BODY).apply { setText(it) }) }
            return
        }
        // Longest first: the question is what he is watching, and the answer is at the top.
        val ordered = shown.entries.sortedByDescending { it.value }.take(MOST)
        val longest = ordered.first().value.coerceAtLeast(1)
        ordered.forEach { (pkg, seconds) ->
            val name = names[pkg] ?: service?.labels?.labelOf(pkg) ?: pkg
            into.addView(row(name, seconds, longest))
        }
    }

    private fun row(name: String, seconds: Int, longest: Int) = LinearLayout(context).apply {
        orientation = LinearLayout.HORIZONTAL
        gravity = Gravity.CENTER_VERTICAL
        minimumHeight = context.dp(ROW_DP)
        addView(
            context.tvText(TextRole.BODY, Palette.TEXT).apply {
                text = name
                maxLines = 1
                ellipsize = TextUtils.TruncateAt.END
            },
            LinearLayout.LayoutParams(context.dp(NAME_WIDTH_DP), WRAP),
        )
        addView(
            TvMeter(context, BAR_DP).apply { show(seconds.toLong(), longest.toLong()) },
            LinearLayout.LayoutParams(0, context.dp(BAR_DP), 1f),
        )
        addView(
            context.tvText(TextRole.BODY).apply {
                text = TvStyle.length(context, seconds)
                gravity = Gravity.END
                maxLines = 1
            },
            LinearLayout.LayoutParams(context.dp(TIME_WIDTH_DP), WRAP),
        )
    }

    private fun heading(labelRes: Int, first: Boolean) = context.tvText(TextRole.HEADLINE).apply {
        setText(labelRes)
        setPadding(0, if (first) 0 else context.dp(Spacing.XXL), 0, context.dp(Spacing.M))
    }

    private companion object {
        /** Enough to answer the question. A television with thirty apps does not need thirty rows. */
        const val MOST = 6
        const val WRAP = LinearLayout.LayoutParams.WRAP_CONTENT
        const val ROW_DP = 40
        const val NAME_WIDTH_DP = 200
        const val TIME_WIDTH_DP = 120
        const val BAR_DP = 12
    }
}
