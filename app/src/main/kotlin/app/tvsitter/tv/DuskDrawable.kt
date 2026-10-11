/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.tv

import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.ColorFilter
import android.graphics.Paint
import android.graphics.PixelFormat
import android.graphics.Rect
import android.graphics.drawable.Drawable
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import android.util.Log
import app.tvsitter.rules.Dusk
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.Executors

/**
 * [Dusk] as a background: the dithered pixels at exactly the size drawn, so nothing scales them.
 *
 * A GradientDrawable showed the glow as stripes on the television, because it has no dither and
 * the two colours are only about twenty steps apart. Scaling a smaller dithered picture up would
 * bring the stripes back, which is why this is made at full size.
 *
 * Made off the main thread, and until it is ready the outer colour fills the bounds. Measured on
 * the TA5, rendering a full screen on the main thread took longer than the five seconds Android
 * allows a window to take focus: the lock went up, did not answer, and the system killed the
 * process as not responding — then held its restart back for half an hour. A backdrop must never
 * be the reason a lock is down.
 */
class DuskDrawable(private val dusk: Dusk) : Drawable() {

    private var picture: Bitmap? = null
    private var wanted: Key? = null
    private val plain = Paint().apply { color = dusk.outer }

    override fun onBoundsChange(bounds: Rect) {
        if (bounds.isEmpty) {
            picture = null
            wanted = null
            return
        }
        val key = Key(bounds.width(), bounds.height(), dusk)
        wanted = key
        picture = CACHE[key]
        if (picture == null) {
            request(key) { ready ->
                // A resize while it was being made asks for a different picture.
                if (wanted == key) {
                    picture = ready
                    invalidateSelf()
                }
            }
        }
    }

    override fun draw(canvas: Canvas) {
        val ready = picture
        if (ready != null) {
            canvas.drawBitmap(ready, null, bounds, null)
        } else {
            canvas.drawRect(bounds, plain)
        }
    }

    override fun setAlpha(alpha: Int) = Unit

    override fun setColorFilter(colorFilter: ColorFilter?) = Unit

    @Deprecated("Deprecated in Java")
    override fun getOpacity(): Int = PixelFormat.OPAQUE

    private data class Key(val width: Int, val height: Int, val dusk: Dusk)

    private companion object {
        /** One screen size in practice, shared by the lock screen and the PIN screen. */
        val CACHE = ConcurrentHashMap<Key, Bitmap>()

        /** Who is waiting for a picture being made. Touched on the main thread only. */
        val WAITING = HashMap<Key, MutableList<(Bitmap) -> Unit>>()

        val MAIN = Handler(Looper.getMainLooper())

        /** One thread, lowest priority: the picture is decoration, and it can wait its turn. */
        val WORKER = Executors.newSingleThreadExecutor { work ->
            Thread(work, "dusk").apply {
                isDaemon = true
                priority = Thread.MIN_PRIORITY
            }
        }

        fun request(key: Key, onReady: (Bitmap) -> Unit) {
            if (Looper.myLooper() != Looper.getMainLooper()) {
                MAIN.post { request(key, onReady) }
                return
            }
            CACHE[key]?.let {
                onReady(it)
                return
            }
            WAITING[key]?.let {
                it += onReady
                return
            }
            WAITING[key] = mutableListOf(onReady)
            WORKER.execute {
                // Caught: a picture that cannot be made leaves the plain fill, never a crash.
                val started = SystemClock.elapsedRealtime()
                val made = runCatching {
                    val pixels = key.dusk.render(key.width, key.height)
                    Bitmap.createBitmap(pixels, key.width, key.height, Bitmap.Config.ARGB_8888)
                }.onSuccess {
                    val took = SystemClock.elapsedRealtime() - started
                    Log.i(EnforcerService.TAG, "backdrop: ${key.width}x${key.height} in ${took}ms")
                }.onFailure { Log.w(EnforcerService.TAG, "backdrop: could not render", it) }.getOrNull()
                MAIN.post {
                    val waiting = WAITING.remove(key).orEmpty()
                    if (made != null) {
                        CACHE[key] = made
                        waiting.forEach { it(made) }
                    }
                }
            }
        }
    }
}
