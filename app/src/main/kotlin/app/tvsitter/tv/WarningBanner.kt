/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.tv

import android.content.Context
import android.graphics.PixelFormat
import android.os.Handler
import android.os.Looper
import android.util.Log
import android.util.TypedValue
import android.view.Gravity
import android.view.View
import android.view.WindowManager
import android.widget.TextView

/**
 * A line at the top of the screen saying time is nearly up, which then goes away.
 *
 * Not a lock and deliberately unlike one. The lock takes focus so a child cannot navigate
 * behind it; this must not, or a warning would steal the remote in the middle of a programme.
 * `FLAG_NOT_FOCUSABLE` and `FLAG_NOT_TOUCHABLE` together mean it is seen and nothing else.
 *
 * It is also not a Toast. A toast is short, easy to miss on a television from across a room,
 * and cannot be held on screen long enough to be read by somebody who was watching rather
 * than waiting for it.
 */
class WarningBanner(private val context: Context) {

    private val windowManager = context.getSystemService(WindowManager::class.java)
    private val handler = Handler(Looper.getMainLooper())
    private var root: View? = null
    private val dismiss = Runnable { hide() }

    val isShowing: Boolean get() = root != null

    /** Shows [message] for [VISIBLE_MS], replacing anything already up. */
    fun show(message: String) {
        val existing = root
        if (existing is TextView) {
            // Logged as loudly as a new banner. Without this the replacement was silent, and a
            // refusal arriving while a "waiting for an answer" banner was still up looked from
            // the log exactly like a refusal that did nothing (#76).
            Log.i(EnforcerService.TAG, "warning replaced: $message")
            existing.text = message
            restartTimer()
            return
        }

        val banner = TextView(context).apply {
            text = message
            setTextColor(TEXT_COLOR)
            setBackgroundColor(BACKDROP_COLOR)
            setTextSize(TypedValue.COMPLEX_UNIT_SP, TEXT_SP)
            gravity = Gravity.CENTER
            setPadding(PADDING_PX, PADDING_PX, PADDING_PX, PADDING_PX)
        }

        val added = runCatching { windowManager.addView(banner, layoutParams()) }
        if (added.isFailure) {
            Log.e(EnforcerService.TAG, "addView() failed for the warning", added.exceptionOrNull())
            return
        }
        root = banner
        restartTimer()
        Log.i(EnforcerService.TAG, "warning shown: $message")
    }

    fun hide() {
        handler.removeCallbacks(dismiss)
        val view = root ?: return
        runCatching { windowManager.removeViewImmediate(view) }
            .onFailure { Log.w(EnforcerService.TAG, "removeView() failed for the warning", it) }
        root = null
    }

    private fun restartTimer() {
        handler.removeCallbacks(dismiss)
        handler.postDelayed(dismiss, VISIBLE_MS)
    }

    private fun layoutParams() = WindowManager.LayoutParams(
        WindowManager.LayoutParams.MATCH_PARENT,
        WindowManager.LayoutParams.WRAP_CONTENT,
        WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
        // The opposite choice from the lock, and for the opposite reason: this one must not
        // take focus or touches, so the remote keeps working while it is up.
        WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or
            WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE or
            WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN,
        PixelFormat.TRANSLUCENT,
    ).apply {
        gravity = Gravity.TOP
        // Overscan is real on some sets, so it does not sit against the very edge.
        y = TOP_MARGIN_PX
    }

    private companion object {
        const val VISIBLE_MS = 12_000L
        const val TEXT_SP = 22f
        const val PADDING_PX = 28
        const val TOP_MARGIN_PX = 48
        const val TEXT_COLOR = 0xFFFFFFFF.toInt()

        // Nearly opaque rather than fully: this sits over whatever is playing, and a solid
        // band across the top of a film is more intrusive than the warning needs to be.
        const val BACKDROP_COLOR = 0xE60B1017.toInt()
    }
}
