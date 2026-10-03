/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.tv

import android.content.Context
import android.graphics.drawable.Drawable
import android.graphics.drawable.GradientDrawable
import android.graphics.drawable.LayerDrawable
import android.util.TypedValue
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.view.animation.DecelerateInterpolator
import android.widget.Button

/** What a control looks like while it is not the cursor. */
enum class Rest(val fill: Int, val edge: Int) {
    /** The ordinary control: a raised plate. */
    FILLED(Palette.RAISED, Palette.CLEAR),

    /** A second choice beside a first one — there, but not asking to be pressed. */
    QUIET(Palette.CLEAR, Palette.EDGE),

    /** The rail's current destination, while the focus is somewhere else. */
    CURRENT(Palette.ACCENT_DIM, Palette.CLEAR),

    /** Nothing at all until it is pointed at. */
    BARE(Palette.CLEAR, Palette.CLEAR),
}

/**
 * The cursor, which on a television is the whole interface.
 *
 * With a D-pad the focused element is the only pointer there is: if it cannot be found from across
 * the room, the screen is broken however pretty it is. So three things change at once, because one
 * signal does not survive a washed-out panel in a bright room — the plate turns near-white (the
 * brightest thing on any screen), it grows a little, and a mint ring appears around it with a gap
 * of backdrop in between, which keeps the ring legible against a white plate and a dark screen
 * alike.
 *
 * The ring is drawn inside the control's own bounds, in space every control reserves whether it
 * is focused or not. A ring drawn outside would be clipped by the parent, which is the bug the
 * old focus treatment had down its left edge; one that changed the control's size would make the
 * whole column jump when the cursor moved.
 *
 * Shouting is off. A child reading block capitals is being told off by a machine.
 */
object TvFocus {
    private const val HALO_DP = 3
    private const val HALO_GAP_DP = 3

    /** Room every focusable control keeps on each side for the ring. */
    const val HALO_SPACE_DP = HALO_DP + HALO_GAP_DP

    private const val SCALE = 1.05f
    private const val MS = 150L

    private const val BUTTON_PAD_X_DP = 30
    private const val BUTTON_PAD_Y_DP = 18
    private const val EDGE_DP = 2

    /** A button that reads from a sofa and is obviously the cursor when it is. */
    fun dress(button: Button, rest: Rest = Rest.FILLED) {
        val context = button.context
        button.isAllCaps = false
        button.stateListAnimator = null
        button.minHeight = 0
        button.minWidth = 0
        button.minimumHeight = 0
        button.minimumWidth = 0
        button.typeface = Fonts.MEDIUM
        button.gravity = Gravity.CENTER
        button.setTextSize(TypedValue.COMPLEX_UNIT_SP, TypeScale.BUTTON)
        val haloSpace = context.dp(HALO_SPACE_DP)
        button.setPadding(
            haloSpace + context.dp(BUTTON_PAD_X_DP),
            haloSpace + context.dp(BUTTON_PAD_Y_DP),
            haloSpace + context.dp(BUTTON_PAD_X_DP),
            haloSpace + context.dp(BUTTON_PAD_Y_DP),
        )
        follow(button, rest) { focused ->
            button.setTextColor(
                when {
                    focused -> Palette.ON_LIT
                    rest == Rest.QUIET -> Palette.SECONDARY
                    else -> Palette.TEXT
                },
            )
        }
    }

    /**
     * Paints [view] for both states from now on, and tells [onChange] so it can recolour what is
     * inside it — a label on a white plate has to turn dark at the same moment.
     */
    fun follow(view: View, rest: Rest, radiusDp: Int = Radius.M, onChange: (Boolean) -> Unit = {}) {
        val paint = { focused: Boolean ->
            view.background = plate(view.context, focused, rest, radiusDp)
            grow(view, focused)
            onChange(focused)
        }
        paint(view.isFocused)
        view.setOnFocusChangeListener { _, focused -> paint(focused) }
    }

    /** The plate behind a control, with the ring when it is the cursor and room for it when not. */
    fun plate(context: Context, focused: Boolean, rest: Rest, radiusDp: Int = Radius.M): Drawable {
        val halo = context.dp(HALO_DP)
        val space = context.dp(HALO_SPACE_DP)
        val radius = context.dp(radiusDp.toFloat())
        val ring = GradientDrawable().apply {
            cornerRadius = radius + space
            setColor(Palette.CLEAR)
            if (focused) setStroke(halo, Palette.ACCENT)
        }
        val face = GradientDrawable().apply {
            cornerRadius = radius
            setColor(if (focused) Palette.LIT else rest.fill)
            if (!focused && rest.edge != Palette.CLEAR) setStroke(context.dp(EDGE_DP), rest.edge)
        }
        return LayerDrawable(arrayOf(ring, face)).apply { setLayerInset(1, space, space, space, space) }
    }

    /** Eased rather than snapped: a cursor that teleports is easy to lose between frames. */
    fun grow(view: View, focused: Boolean) {
        val scale = if (focused) SCALE else 1f
        view.animate()
            .scaleX(scale)
            .scaleY(scale)
            .setDuration(MS)
            .setInterpolator(DecelerateInterpolator())
            .start()
    }

    /**
     * Lets a focused child grow past its parent's edges.
     *
     * Without this the scale-up is clipped by the container's padding, and a button at the left
     * margin loses the very corner that shows it is a button — measured on the setup screen,
     * where the focused one looked cut off down its left side.
     */
    fun letFocusOverflow(group: ViewGroup) {
        group.clipChildren = false
        group.clipToPadding = false
    }
}
