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
 * The start destination, and the screen somebody walks up to the television for.
 *
 * It answers four things in the order they are asked: is it working, how much has been watched
 * today, what is in force, and is the lock up. Nothing else — the detail is in Statistics and the
 * controls are in Settings, which is the whole point of the app having a shape (#110).
 */
class TodayPanel(private val context: Context) {

    private val heading = text(TvStyle.HEADING_SP, TvStyle.TEXT)
    private val used = text(TvStyle.NUMBER_SP, TvStyle.TEXT)
    private val limit = text(TvStyle.NUMBER_SP, TvStyle.TEXT)

    // Not `left`: inside a View's apply block that is View.left, an Int, and the shadowing
    // is silent until the types happen to disagree.
    private val remaining = text(TvStyle.NUMBER_SP, TvStyle.ACCENT)
    private val inForce = text(TvStyle.BODY_SP, TvStyle.MUTED)
    private val attention = text(TvStyle.BODY_SP, TvStyle.WARN)

    val view: View = LinearLayout(context).apply {
        orientation = LinearLayout.VERTICAL
        setPadding(TvStyle.OVERSCAN_PX, TvStyle.OVERSCAN_PX, TvStyle.OVERSCAN_PX, TvStyle.OVERSCAN_PX)
        addView(heading)
        addView(
            LinearLayout(context).apply {
                orientation = LinearLayout.HORIZONTAL
                setPadding(0, TvStyle.GAP_PX, 0, TvStyle.GAP_PX)
                listOf(
                    column(used, R.string.setup_used),
                    column(limit, R.string.setup_limit),
                    column(remaining, R.string.setup_left),
                ).forEach { addView(it) }
            },
        )
        addView(inForce)
        addView(attention)
    }

    fun refresh() {
        val service = EnforcerService.instance
        val trouble = Trouble.of(context, service)

        heading.text = context.getString(
            if (trouble.isEmpty()) R.string.setup_all_well else R.string.setup_attention,
        )
        heading.setTextColor(if (trouble.isEmpty()) TvStyle.TEXT else TvStyle.WARN)

        used.text = TvStyle.length(context, service?.usedTodaySeconds)
        val aside = service?.limitSetAside == true
        limit.text = service?.limitTodaySeconds?.let { TvStyle.length(context, it) }
            ?: context.getString(if (aside) R.string.setup_set_aside else R.string.setup_no_limit)
        remaining.text = service?.remainingTodaySeconds?.let { TvStyle.length(context, it) }
            ?: context.getString(R.string.setup_no_limit)

        inForce.text = context.getString(
            if (service?.isReporting == true) R.string.pair_done else R.string.pair_offline,
        )

        attention.text = trouble.joinToString(separator = "\n\n")
        attention.visibility = if (trouble.isEmpty()) View.GONE else View.VISIBLE
    }

    private fun column(value: TextView, labelRes: Int) = LinearLayout(context).apply {
        orientation = LinearLayout.VERTICAL
        setPadding(0, 0, TvStyle.OVERSCAN_PX, 0)
        addView(value)
        addView(text(TvStyle.SMALL_SP, TvStyle.MUTED).apply { setText(labelRes) })
    }

    private fun text(sizeSp: Float, colour: Int) = TextView(context).apply {
        setTextColor(colour)
        setTextSize(android.util.TypedValue.COMPLEX_UNIT_SP, sizeSp)
    }
}

/**
 * What is wrong, in words, with what to do about it.
 *
 * Its own thing because two screens ask: Today shows it because it is the first question, and
 * Settings shows it because that is where somebody goes to act on it.
 *
 * A permission that is granted is not news. Nine lines of "yes" with one "no" among them is how a
 * screen hides the only thing on it that matters, which is what the old one did.
 */
object Trouble {
    fun of(context: Context, service: EnforcerService?): List<String> = buildList {
        if (service == null) add(context.getString(R.string.setup_fix_service))
        if (!Permissions.canDrawOverlays(context)) add(context.getString(R.string.setup_fix_overlay))
        if (!Permissions.hasUsageAccess(context)) add(context.getString(R.string.setup_fix_usage))
        if (service != null && !service.isReporting) {
            add(context.getString(R.string.setup_fix_reporting))
        }
        if (service?.isLocked == true) add(context.getString(R.string.setup_locked_now))
    }
}
