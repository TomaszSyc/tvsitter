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
import app.tvsitter.rules.Window
import java.time.format.DateTimeFormatter

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
    private val hours = text(TvStyle.BODY_SP, TvStyle.MUTED)
    private val watching = text(TvStyle.BODY_SP, TvStyle.MUTED)
    private val locked = text(TvStyle.HEADING_SP, TvStyle.WARN)
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
        addView(hours)
        addView(watching)
        addView(locked.apply { setPadding(0, TvStyle.GAP_PX, 0, 0) })
        addView(attention.apply { setPadding(0, TvStyle.GAP_PX, 0, 0) })
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

        showWhatIsInForce(service)

        // The lock in the words the child is reading at that moment, rather than a second
        // wording of the same fact one room away.
        locked.text = service?.lockTitle?.let { context.getString(R.string.today_locked, it) }.orEmpty()
        locked.visibility = if (service?.lockTitle != null) View.VISIBLE else View.GONE

        attention.text = trouble.joinToString(separator = "\n\n")
        attention.visibility = if (trouble.isEmpty()) View.GONE else View.VISIBLE
    }

    /**
     * What is being enforced today, as sentences rather than a table.
     *
     * The limit, whether it was set aside, and the hours if any window applies — the three
     * things that answer "why did it stop" before it stops. This line used to repeat whether the
     * television was reaching Home Assistant, which is a question about the plumbing and already
     * has its own line below when it is going wrong.
     */
    private fun showWhatIsInForce(service: EnforcerService?) {
        if (service == null) {
            listOf(inForce, hours, watching).forEach { it.visibility = View.GONE }
            return
        }
        listOf(inForce, hours).forEach { it.visibility = View.VISIBLE }

        inForce.text = when {
            service.limitSetAside -> context.getString(R.string.today_limit_aside)
            service.limitTodaySeconds == null -> context.getString(R.string.today_limit_none)
            else -> context.getString(
                R.string.today_limit,
                TvStyle.length(context, service.limitTodaySeconds),
            )
        }

        // No window applying today is no restriction, not a closed day — the reading the engine
        // has had since M4 (D27), said out loud so nobody has to infer it from an empty line.
        val today = service.rules.windows.filter { it.appliesOn(service.budgetDay) }
        hours.text = if (today.isEmpty()) {
            context.getString(R.string.today_hours_any)
        } else {
            context.getString(R.string.today_hours, today.joinToString(", ") { span(it) })
        }

        val app = service.foregroundPackage?.let { service.labels?.labelOf(it) ?: it }
        watching.text = app?.let { context.getString(R.string.today_watching, it) }.orEmpty()
        watching.visibility = if (app == null) View.GONE else View.VISIBLE
    }

    /** `16:00–19:30`, with an en dash because it is a range rather than a subtraction. */
    private fun span(window: Window): String =
        "${window.from.format(HOUR_AND_MINUTE)}\u2013${window.to.format(HOUR_AND_MINUTE)}"

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

    private companion object {
        val HOUR_AND_MINUTE: DateTimeFormatter = DateTimeFormatter.ofPattern("HH:mm")
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
    }
}
