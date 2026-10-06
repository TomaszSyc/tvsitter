/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.tv

import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.ColorFilter
import android.graphics.PixelFormat
import android.graphics.Rect
import android.graphics.drawable.Drawable
import app.tvsitter.rules.Dusk

/**
 * [Dusk] as a background: the dithered pixels at exactly the size drawn, so nothing scales them.
 *
 * A GradientDrawable showed the glow as stripes on the television, because it has no dither and
 * the two colours are only about twenty steps apart. Scaling a smaller dithered picture up would
 * bring the stripes back, which is why this is made at full size.
 */
class DuskDrawable(private val dusk: Dusk) : Drawable() {

    private var picture: Bitmap? = null

    override fun onBoundsChange(bounds: Rect) {
        picture = if (bounds.isEmpty) null else cached(bounds.width(), bounds.height())
    }

    override fun draw(canvas: Canvas) {
        picture?.let { canvas.drawBitmap(it, null, bounds, null) }
    }

    override fun setAlpha(alpha: Int) = Unit

    override fun setColorFilter(colorFilter: ColorFilter?) = Unit

    @Deprecated("Deprecated in Java")
    override fun getOpacity(): Int = PixelFormat.OPAQUE

    private fun cached(width: Int, height: Int): Bitmap = synchronized(CACHE) {
        val key = Key(width, height, dusk)
        // One screen size in practice, and the lock screen and the PIN screen share it, so the
        // couple of hundred milliseconds of working it out are spent once per process.
        CACHE.getOrPut(key) {
            Bitmap.createBitmap(dusk.render(width, height), width, height, Bitmap.Config.ARGB_8888)
        }
    }

    private data class Key(val width: Int, val height: Int, val dusk: Dusk)

    private companion object {
        val CACHE = HashMap<Key, Bitmap>()
    }
}
