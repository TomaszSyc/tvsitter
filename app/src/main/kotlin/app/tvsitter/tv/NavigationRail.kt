/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.tv

import android.content.Context
import android.content.res.ColorStateList
import android.view.Gravity
import android.widget.LinearLayout
import android.widget.TextView

/** Where the app can be, in the order somebody wants them. */
enum class Destination(val labelRes: Int, val iconRes: Int) {
    TODAY(R.string.nav_today, R.drawable.ic_today),
    STATISTICS(R.string.nav_statistics, R.drawable.ic_stats),
    SETTINGS(R.string.nav_settings, R.drawable.ic_settings),
}

/**
 * The side rail: icons always, labels when it has the focus.
 *
 * The platform's guidance is specific about this one, and it is not the mobile drawer: on a
 * television both states are visible to the user rather than one hiding the other, the rail
 * stays put while the content changes, and five or six destinations is the ceiling. Three is
 * comfortably under it.
 *
 * Icons on every item, because a rail of bare words is the thing the guidance names as wrong —
 * and because at three metres a shape is read before a label is.
 *
 * Built from views rather than the Compose components the documentation shows. The pattern is
 * what the guidance is about; the toolkit is how it gets drawn, and rewriting every screen in
 * this app to reach for a drawer would be the tail wagging the dog. That decision is recorded
 * rather than assumed (#109).
 */
class NavigationRail(context: Context, private val onChosen: (Destination) -> Unit) : LinearLayout(context) {

    /** The app's mark, and its name while the rail is open. Not focusable: it goes nowhere. */
    private val brand = context.tvText(TextRole.STRONG, Palette.TEXT).apply {
        setCompoundDrawablesRelativeWithIntrinsicBounds(R.drawable.ic_mark, 0, 0, 0)
        compoundDrawablePadding = context.dp(Spacing.M)
        gravity = Gravity.CENTER_VERTICAL
        textSize = TypeScale.BUTTON
        val inset = context.dp(TvFocus.HALO_SPACE_DP + BRAND_INSET_DP)
        setPadding(inset, 0, inset, context.dp(Spacing.XL))
    }

    private val items = Destination.entries.associateWith { item(it) }

    private var current = Destination.TODAY

    init {
        orientation = VERTICAL
        setBackgroundColor(Palette.SURFACE)
        setPadding(context.dp(RAIL_PADDING_DP), context.dp(Spacing.SAFE_Y), context.dp(RAIL_PADDING_DP), 0)
        TvFocus.letFocusOverflow(this)
        addView(brand)
        items.values.forEach { addView(it) }
        select(Destination.TODAY)
    }

    /** Moves the highlight, without pretending anybody pressed anything. */
    fun select(destination: Destination) {
        current = destination
        repaint()
    }

    fun focusCurrent() {
        items[current]?.requestFocus()
    }

    private fun item(destination: Destination): TextView = context.tvText(TextRole.STRONG).apply {
        setCompoundDrawablesRelativeWithIntrinsicBounds(destination.iconRes, 0, 0, 0)
        compoundDrawablePadding = context.dp(Spacing.L)
        gravity = Gravity.CENTER_VERTICAL
        isFocusable = true
        isFocusableInTouchMode = true
        maxLines = 1
        val halo = context.dp(TvFocus.HALO_SPACE_DP)
        setPadding(
            halo + context.dp(ITEM_PADDING_X_DP),
            halo + context.dp(ITEM_PADDING_Y_DP),
            halo + context.dp(ITEM_PADDING_X_DP),
            halo + context.dp(ITEM_PADDING_Y_DP),
        )
        setOnFocusChangeListener { _, _ -> repaint() }
        setOnClickListener { onChosen(destination) }
    }

    /**
     * Both states of the rail, drawn from one place so they cannot disagree.
     *
     * The collapse has to remove the label rather than squeeze it. Making the item narrower and
     * leaving the text in it is what put the icons out of line — the label was still being
     * measured, so it pushed the icon along and then got clipped. Reported from use, and visible
     * only on the screen that happened to move focus off the rail.
     */
    private fun repaint() {
        val expanded = items.values.any { it.isFocused }
        brand.text = if (expanded) context.getString(R.string.app_name) else ""
        items.forEach { (destination, view) ->
            val chosen = destination == current
            view.text = if (expanded) context.getString(destination.labelRes) else ""
            view.width = context.dp(if (expanded) EXPANDED_DP else COLLAPSED_DP)
            val ink = when {
                view.isFocused -> Palette.ON_LIT
                chosen -> Palette.TEXT
                else -> Palette.TERTIARY
            }
            view.setTextColor(ink)
            view.compoundDrawableTintList = ColorStateList.valueOf(
                if (chosen && !view.isFocused) Palette.ACCENT else ink,
            )
            view.background = TvFocus.plate(
                context,
                view.isFocused,
                if (chosen) Rest.CURRENT else Rest.BARE,
            )
            TvFocus.grow(view, view.isFocused)
        }
    }

    private companion object {
        const val RAIL_PADDING_DP = 10

        /** Puts the mark's centre on the icons' centre line below it. */
        const val BRAND_INSET_DP = 8
        const val ITEM_PADDING_X_DP = 14
        const val ITEM_PADDING_Y_DP = 14

        /** The icon and its padding, with the halo's room on both sides. */
        const val COLLAPSED_DP = 64
        const val EXPANDED_DP = 216
    }
}
