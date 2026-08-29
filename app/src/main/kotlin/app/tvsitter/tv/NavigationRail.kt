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

    private val items = Destination.entries.associateWith { item(it) }

    private var current = Destination.TODAY

    init {
        orientation = VERTICAL
        setBackgroundColor(TvStyle.SURFACE)
        setPadding(RAIL_PADDING_PX, TvStyle.OVERSCAN_PX, RAIL_PADDING_PX, TvStyle.OVERSCAN_PX)
        TvStyle.letFocusOverflow(this)
        items.values.forEach { addView(it) }
        select(Destination.TODAY)
    }

    /** Moves the highlight, without pretending anybody pressed anything. */
    fun select(destination: Destination) {
        current = destination
        items.forEach { (which, view) -> view.paint(chosen = which == destination) }
    }

    fun focusCurrent() {
        items[current]?.requestFocus()
    }

    private fun item(destination: Destination): TextView = TextView(context).apply {
        text = context.getString(destination.labelRes)
        setCompoundDrawablesRelativeWithIntrinsicBounds(destination.iconRes, 0, 0, 0)
        compoundDrawablePadding = ICON_GAP_PX
        gravity = Gravity.CENTER_VERTICAL
        isFocusable = true
        isFocusableInTouchMode = true
        setPadding(ITEM_PADDING_PX, ITEM_PADDING_PX, ITEM_PADDING_PX, ITEM_PADDING_PX)
        // Labels appear when the rail has the focus and go again when it does not, which is the
        // collapsed and expanded pair the guidance describes rather than a drawer that slides.
        setOnFocusChangeListener { _, _ -> items.values.forEach { it.paint(it.isChosen()) } }
        setOnClickListener { onChosen(destination) }
    }

    private fun TextView.isChosen(): Boolean = text == context.getString(current.labelRes)

    private fun TextView.paint(chosen: Boolean) {
        val expanded = items.values.any { it.isFocused }
        // Text is what makes the rail wide, so hiding it is what collapses it. The icon stays,
        // which is the whole point of a rail rather than a menu that appears and disappears.
        setTextColor(if (chosen || isFocused) TvStyle.TEXT else TvStyle.MUTED)
        setTextSize(android.util.TypedValue.COMPLEX_UNIT_SP, TvStyle.SMALL_SP)
        visibility = View.VISIBLE
        width = if (expanded) EXPANDED_PX else COLLAPSED_PX
        background = GradientDrawable().apply {
            cornerRadius = ITEM_RADIUS_PX
            setColor(
                when {
                    isFocused -> TvStyle.ACCENT
                    chosen -> TvStyle.ACTIVE
                    else -> TvStyle.SURFACE
                },
            )
        }
        if (isFocused) setTextColor(TvStyle.BACKDROP)
    }

    private companion object {
        const val RAIL_PADDING_PX = 16
        const val ITEM_PADDING_PX = 24
        const val ICON_GAP_PX = 24
        const val ITEM_RADIUS_PX = 28f
        const val COLLAPSED_PX = 120
        const val EXPANDED_PX = 380
    }
}
