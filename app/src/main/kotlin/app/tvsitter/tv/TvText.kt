/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.tv

import android.content.Context
import android.content.res.ColorStateList
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.util.TypedValue
import android.view.Gravity
import android.widget.FrameLayout
import android.widget.ImageView
import android.widget.TextView
import app.tvsitter.rules.Dusk

/**
 * The system's own Roboto, in the two weights the scale uses.
 *
 * Not a bundled face: the set already has this one, it is drawn well at television sizes, and a
 * font file in the APK is a thing to license and keep current for no gain a child would notice.
 */
object Fonts {
    val REGULAR: Typeface = Typeface.create("sans-serif", Typeface.NORMAL)
    val MEDIUM: Typeface = Typeface.create("sans-serif-medium", Typeface.NORMAL)
}

/** Each kind of text on a screen, so a size never travels without its weight and colour. */
enum class TextRole(val sizeSp: Float, val medium: Boolean, val colour: Int, val tracking: Float = 0f) {
    DISPLAY(TypeScale.DISPLAY, medium = false, colour = Palette.TEXT, tracking = -0.01f),
    LEAD(TypeScale.LEAD, medium = false, colour = Palette.SECONDARY),
    HEADLINE(TypeScale.HEADLINE, medium = true, colour = Palette.TEXT),
    TITLE(TypeScale.TITLE, medium = false, colour = Palette.TEXT),
    STRONG(TypeScale.BODY, medium = true, colour = Palette.TEXT),
    BODY(TypeScale.BODY, medium = false, colour = Palette.SECONDARY),
    LABEL(TypeScale.LABEL, medium = true, colour = Palette.TERTIARY, tracking = 0.02f),

    /** Section names. Capitals here are a signpost rather than a raised voice. */
    OVERLINE(TypeScale.LABEL, medium = true, colour = Palette.ACCENT, tracking = 0.12f),
    NUMBER(TypeScale.NUMBER, medium = true, colour = Palette.TEXT),
    CODE(TypeScale.CODE, medium = true, colour = Palette.ACCENT, tracking = 0.08f),
}

private const val LINE_SPACING = 1.15f

fun Context.tvText(role: TextRole, colour: Int = role.colour): TextView = TextView(this).apply {
    setTextColor(colour)
    setTextSize(TypedValue.COMPLEX_UNIT_SP, role.sizeSp)
    typeface = if (role.medium) Fonts.MEDIUM else Fonts.REGULAR
    letterSpacing = role.tracking
    setLineSpacing(0f, LINE_SPACING)
    isAllCaps = role == TextRole.OVERLINE
    // Tabular figures, so a countdown or a column of durations does not shimmer as it changes.
    fontFeatureSettings = "tnum"
}

/** A rounded plate in one colour — a card, a chip, a track. */
fun Context.plate(colour: Int, radiusDp: Int, edge: Int = Palette.CLEAR): GradientDrawable = GradientDrawable().apply {
    cornerRadius = dp(radiusDp.toFloat())
    setColor(colour)
    if (edge != Palette.CLEAR) setStroke(dp(1), edge)
}

/**
 * The backdrop of a whole screen: ink, lit faintly from above.
 *
 * Opaque from edge to edge — both ends of the gradient are — so it hides whatever is behind it as
 * completely as a flat colour does. The glow's centre sits above the top edge, so only its lower
 * rim reaches the screen and nothing is ever drawn on the bright part.
 */
fun Context.dusk(): DuskDrawable =
    DuskDrawable(Dusk(Palette.DUSK, Palette.INK, DUSK_CENTRE_X, DUSK_CENTRE_Y, dp(DUSK_RADIUS_DP.toFloat())))

private const val DUSK_CENTRE_X = 0.5f
private const val DUSK_CENTRE_Y = -0.1f
private const val DUSK_RADIUS_DP = 720

/**
 * The dial from the app's own mark, a day with part of it spent, on a mint-tinted disc.
 *
 * The lock and the warning both carry it, so the warning reads as the lock's advance notice. One
 * picture for every reason, because the words already say which one it is, and a sad face or a
 * moon would be the television having an opinion about it.
 */
fun Context.dialBadge(sizeDp: Int, iconDp: Int): FrameLayout = FrameLayout(this).apply {
    background = dot(Palette.ACCENT_DIM, sizeDp)
    addView(
        ImageView(context).apply {
            setImageResource(R.drawable.ic_today)
            imageTintList = ColorStateList.valueOf(Palette.ACCENT)
        },
        FrameLayout.LayoutParams(dp(iconDp), dp(iconDp), Gravity.CENTER),
    )
}

/** A filled circle, or a ring when [filled] is false, [sizeDp] across. */
fun Context.dot(colour: Int, sizeDp: Int, filled: Boolean = true): GradientDrawable = GradientDrawable().apply {
    shape = GradientDrawable.OVAL
    setSize(dp(sizeDp), dp(sizeDp))
    if (filled) setColor(colour) else setStroke(dp(2), colour)
}
