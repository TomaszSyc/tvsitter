/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.rules

import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test
import kotlin.math.abs

class DuskTest {

    private val inner = 0xFF11272D.toInt()
    private val outer = 0xFF0B1117.toInt()

    // The lock screen at full size: 1920x1080 with the glow's centre above the top edge.
    private val width = 1920
    private val height = 1080
    private val dusk = Dusk(inner, outer, centreX = 0.5f, centreY = -0.1f, radiusPx = 1440f)
    private val pixels = dusk.render(width, height)

    private fun green(x: Int, y: Int) = (pixels[y * width + x] shr 8) and 0xFF

    @Test
    fun `no band of one colour runs on down the screen`() {
        // Undithered, 22 levels over 1440 px leave stripes about 65 px tall, which is the
        // stepping that showed on the television.
        var longest = 0
        var run = 1
        for (y in 1 until height) {
            run = if (green(width / 2, y) == green(width / 2, y - 1)) run + 1 else 1
            longest = maxOf(longest, run)
        }

        assertTrue(longest <= MAX_RUN, "a run of $longest identical pixels")
    }

    @Test
    fun `the dither moves no colour, on average`() {
        // Over a whole row, the dithered pixels and the unrounded gradient have to agree.
        val y = 400
        val mean = (0 until width).map { green(it, y) }.average()
        val exact = (0 until width)
            .map { dusk.exactChannel(it, y, width, height, shift = 8) }
            .average()

        assertTrue(abs(mean - exact) < MAX_DRIFT, "mean $mean against $exact")
    }

    @Test
    fun `past the glow it is the outer colour exactly`() {
        val far = Dusk(inner, outer, centreX = 0.5f, centreY = -10f, radiusPx = 10f).render(64, 64)

        assertTrue(far.all { it == outer })
    }

    @Test
    fun `every pixel is opaque, so the lock still hides the screen`() {
        assertTrue(pixels.all { (it ushr 24) == 0xFF })
    }

    @Test
    fun `the same size draws the same picture`() {
        val small = Dusk(inner, outer, 0.5f, -0.1f, 40f)

        assertEquals(small.render(32, 32).toList(), small.render(32, 32).toList())
    }

    private companion object {
        const val MAX_RUN = 12
        const val MAX_DRIFT = 0.6
    }
}
