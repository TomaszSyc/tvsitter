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

    private val pip = View(context)
    private val heading = context.tvText(TextRole.HEADLINE)
    private val used = context.tvText(TextRole.NUMBER)
    private val limit = context.tvText(TextRole.NUMBER)

    // Not `left`: inside a View's apply block that is View.left, an Int, and the shadowing
    // is silent until the types happen to disagree.
    private val remaining = context.tvText(TextRole.NUMBER, Palette.ACCENT)
    private val meter = TvMeter(context, METER_DP)
    private val inForce = fact()
    private val hours = fact()
    private val bedtime = fact()
    private val watching = fact()

    // The lock and the trouble are the only warm colour on the screen, so they are found first.
    private val locked = context.tvText(TextRole.STRONG, Palette.WARN).apply {
        background = context.plate(Palette.WARN_DIM, Radius.M)
        setPadding(context.dp(Spacing.XL), context.dp(Spacing.M), context.dp(Spacing.XL), context.dp(Spacing.M))
    }
    private val attention = context.tvText(TextRole.BODY, Palette.WARN).apply {
        background = context.plate(Palette.WARN_DIM, Radius.L)
        setPadding(context.dp(Spacing.XL), context.dp(Spacing.L), context.dp(Spacing.XL), context.dp(Spacing.L))
    }

    val view: View = LinearLayout(context).apply {
        orientation = LinearLayout.VERTICAL
        setPadding(
            context.dp(Spacing.SAFE_X),
            context.dp(Spacing.SAFE_Y),
            context.dp(Spacing.SAFE_X),
            context.dp(Spacing.SAFE_Y),
        )
        addView(status())
        addView(figures(), stacked(Spacing.XL))
        addView(meter, stacked(Spacing.L))
        listOf(inForce, hours, bedtime, watching).forEachIndexed { index, line ->
            addView(line, stacked(if (index == 0) Spacing.XL else Spacing.M))
        }
        addView(locked, stacked(Spacing.XL).apply { width = LinearLayout.LayoutParams.WRAP_CONTENT })
        addView(attention, stacked(Spacing.L))
    }

    fun refresh() {
        val service = EnforcerService.instance
        val trouble = Trouble.of(context, service)

        heading.text = context.getString(
            if (trouble.isEmpty()) R.string.setup_all_well else R.string.setup_attention,
        )
        heading.setTextColor(if (trouble.isEmpty()) Palette.TEXT else Palette.WARN)
        pip.background = context.dot(if (trouble.isEmpty()) Palette.ACCENT else Palette.WARN, PIP_DP)

        showFigures(service)
        showWhatIsInForce(service)

        // The lock in the words the child is reading at that moment, rather than a second
        // wording of the same fact one room away.
        locked.text = service?.lockTitle?.let { context.getString(R.string.today_locked, it) }.orEmpty()
        locked.visibility = if (service?.lockTitle != null) View.VISIBLE else View.GONE

        attention.text = trouble.joinToString(separator = "\n\n")
        attention.visibility = if (trouble.isEmpty()) View.GONE else View.VISIBLE
    }

    private fun showFigures(service: EnforcerService?) {
        used.text = TvStyle.length(context, service?.usedTodaySeconds)
        val aside = service?.limitSetAside == true
        limit.text = service?.limitTodaySeconds?.let { TvStyle.length(context, it) }
            ?: context.getString(if (aside) R.string.setup_set_aside else R.string.setup_no_limit)
        remaining.text = service?.remainingTodaySeconds?.let { TvStyle.length(context, it) }
            ?: context.getString(R.string.setup_no_limit)

        // The same two numbers as the figures above it, drawn: how much of the day is gone is
        // read at a glance from across the room before either number is.
        val cap = service?.limitTodaySeconds
        meter.visibility = if (cap == null) View.GONE else View.VISIBLE
        if (cap != null) meter.show((service?.usedTodaySeconds ?: 0).toLong(), cap.toLong())
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
            listOf(inForce, hours, bedtime, watching).forEach { it.visibility = View.GONE }
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

        // A deadline for tonight is not a rule and is not stored with them (D30), but it is very
        // much in force, and a parent standing here wants to know it is armed before the screen
        // goes dark in ten minutes.
        val sleep = service.sleepInMinutes
        bedtime.text = if (sleep > 0) {
            context.getString(R.string.today_sleep, TvStyle.length(context, sleep * SECONDS_PER_MINUTE))
        } else {
            ""
        }
        bedtime.visibility = if (sleep > 0) View.VISIBLE else View.GONE

        val app = service.foregroundPackage?.let { service.labels?.labelOf(it) ?: it }
        watching.text = app?.let { context.getString(R.string.today_watching, it) }.orEmpty()
        watching.visibility = if (app == null) View.GONE else View.VISIBLE
    }

    /** `16:00–19:30`, with an en dash because it is a range rather than a subtraction. */
    private fun span(window: Window): String =
        "${window.from.format(HOUR_AND_MINUTE)}–${window.to.format(HOUR_AND_MINUTE)}"

    /** A dot that is mint when all is well and amber when not, so the answer is a colour first. */
    private fun status() = LinearLayout(context).apply {
        orientation = LinearLayout.HORIZONTAL
        gravity = Gravity.CENTER_VERTICAL
        addView(pip, LinearLayout.LayoutParams(context.dp(PIP_DP), context.dp(PIP_DP)))
        addView(
            heading,
            LinearLayout.LayoutParams(WRAP, WRAP).apply { marginStart = context.dp(Spacing.M) },
        )
    }

    /**
     * Equal thirds, because the numbers are not the same width and the labels over them have to
     * stay lined up. Left to wrap their content, "4 h 17 min" pushed Limit and Left into the
     * corner and the row read as one number with two dashes after it.
     */
    private fun figures() = LinearLayout(context).apply {
        orientation = LinearLayout.HORIZONTAL
        listOf(
            figure(used, R.string.setup_used),
            figure(limit, R.string.setup_limit),
            figure(remaining, R.string.setup_left),
        ).forEachIndexed { index, card ->
            addView(
                card,
                LinearLayout.LayoutParams(0, WRAP, 1f).apply {
                    if (index > 0) marginStart = context.dp(Spacing.L)
                },
            )
        }
    }

    private fun figure(value: TextView, labelRes: Int) = LinearLayout(context).apply {
        TvStyle.fitNumber(value)
        orientation = LinearLayout.VERTICAL
        background = context.plate(Palette.SURFACE, Radius.L)
        setPadding(context.dp(Spacing.XL), context.dp(FIGURE_PAD_DP), context.dp(Spacing.XL), context.dp(FIGURE_PAD_DP))
        addView(context.tvText(TextRole.LABEL).apply { setText(labelRes) })
        addView(value, stacked(Spacing.XS))
    }

    /** A sentence with a small dot before it, so four facts read as a list and not a paragraph. */
    private fun fact() = context.tvText(TextRole.BODY).apply {
        setCompoundDrawablesRelativeWithIntrinsicBounds(context.dot(Palette.TERTIARY, BULLET_DP), null, null, null)
        compoundDrawablePadding = context.dp(Spacing.L)
        gravity = Gravity.CENTER_VERTICAL
    }

    private fun stacked(gapDp: Int) = LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, WRAP).apply {
        topMargin = context.dp(gapDp)
    }

    private companion object {
        val HOUR_AND_MINUTE: DateTimeFormatter = DateTimeFormatter.ofPattern("HH:mm")
        const val SECONDS_PER_MINUTE = 60
        const val WRAP = LinearLayout.LayoutParams.WRAP_CONTENT
        const val PIP_DP = 14
        const val BULLET_DP = 8
        const val METER_DP = 8
        const val FIGURE_PAD_DP = 20
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
