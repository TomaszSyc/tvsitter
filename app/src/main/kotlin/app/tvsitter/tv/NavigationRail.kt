/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.tv

import android.content.Context
import android.graphics.drawable.GradientDrawable
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
        repaint()
    }

    fun focusCurrent() {
        items[current]?.requestFocus()
    }

    private fun item(destination: Destination): TextView = TextView(context).apply {
        setCompoundDrawablesRelativeWithIntrinsicBounds(destination.iconRes, 0, 0, 0)
        compoundDrawablePadding = ICON_GAP_PX
        gravity = Gravity.CENTER_VERTICAL
        isFocusable = true
        isFocusableInTouchMode = true
        setTextSize(android.util.TypedValue.COMPLEX_UNIT_SP, TvStyle.SMALL_SP)
        setPadding(ITEM_PADDING_PX, ITEM_PADDING_PX, ITEM_PADDING_PX, ITEM_PADDING_PX)
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
        items.forEach { (destination, view) ->
            val chosen = destination == current
            view.text = if (expanded) context.getString(destination.labelRes) else ""
            view.width = if (expanded) EXPANDED_PX else COLLAPSED_PX
            view.setTextColor(
                when {
                    view.isFocused -> TvStyle.BACKDROP
                    chosen -> TvStyle.TEXT
                    else -> TvStyle.MUTED
                },
            )
            view.background = GradientDrawable().apply {
                cornerRadius = ITEM_RADIUS_PX
                setColor(
                    when {
                        view.isFocused -> TvStyle.ACCENT
                        chosen -> TvStyle.ACTIVE
                        else -> TvStyle.SURFACE
                    },
                )
            }
        }
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
