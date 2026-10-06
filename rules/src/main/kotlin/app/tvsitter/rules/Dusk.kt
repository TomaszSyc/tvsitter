/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.rules

import kotlin.math.hypot
import kotlin.math.roundToInt

/**
 * The screens' backdrop as pixels: a radial glow from [inner] fading to [outer], dithered.
 *
 * The two colours are close on purpose, a dark room lit faintly from above, and that leaves eight
 * bits about twenty steps to cover more than a thousand pixels. Drawn plainly, each step is a stripe
 * as tall as a finger on the screen, and the television showed every edge. A fixed 8x8 Bayer pattern
 * moves each pixel by less than one step either way, which turns the edges into a texture far too
 * fine to see while keeping the average colour exactly where the gradient puts it.
 *
 * The centre is a fraction of the size and may lie outside it. Plain Kotlin so the stepping can be
 * measured on the JVM; the app turns the array into a bitmap.
 */
data class Dusk(val inner: Int, val outer: Int, val centreX: Float, val centreY: Float, val radiusPx: Float) {

    /** ARGB pixels, row by row. */
    fun render(width: Int, height: Int): IntArray {
        val pixels = IntArray(width * height)
        for (y in 0 until height) {
            for (x in 0 until width) {
                val t = reach(x, y, width, height)
                val nudge = threshold(x, y)
                pixels[y * width + x] = OPAQUE or
                    (channel(RED, t, nudge) shl RED) or
                    (channel(GREEN, t, nudge) shl GREEN) or
                    channel(BLUE, t, nudge)
            }
        }
        return pixels
    }

    /** One channel at one pixel before rounding, for checking that the dither keeps the average. */
    fun exactChannel(x: Int, y: Int, width: Int, height: Int, shift: Int): Float =
        mix(shift, reach(x, y, width, height))

    /** How far out of the glow a pixel is, from 0 at the centre to 1 at the rim and beyond. */
    private fun reach(x: Int, y: Int, width: Int, height: Int): Float =
        (hypot(x + HALF - centreX * width, y + HALF - centreY * height) / radiusPx).coerceAtMost(1f)

    private fun channel(shift: Int, t: Float, nudge: Float): Int = (mix(shift, t) + nudge).roundToInt().coerceIn(0, MAX)

    private fun mix(shift: Int, t: Float): Float {
        val from = (inner shr shift) and MAX
        val to = (outer shr shift) and MAX
        return from + (to - from) * t
    }

    private companion object {
        const val HALF = 0.5f
        const val MAX = 0xFF
        const val OPAQUE = 0xFF shl 24
        const val RED = 16
        const val GREEN = 8
        const val BLUE = 0

        /** Three bits a side, so an 8x8 pattern of 64 levels. */
        const val BITS = 3
        const val CELLS = 1 shl (2 * BITS)

        /**
         * Strictly between -0.5 and 0.5, so an exact level, the outer colour included, never moves.
         */
        fun threshold(x: Int, y: Int): Float = (bayer(x, y) + HALF) / CELLS - HALF

        /** The ordered-dither matrix: the bits of `x xor y` and `y` interleaved, lowest first. */
        fun bayer(x: Int, y: Int): Int {
            val xy = x xor y
            var value = 0
            for (bit in 0 until BITS) {
                value = (value shl 2) or (((xy shr bit) and 1) shl 1) or ((y shr bit) and 1)
            }
            return value
        }
    }
}
