/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.tv

import android.content.Context
import android.graphics.PixelFormat
import android.graphics.drawable.GradientDrawable
import android.os.Handler
import android.os.Looper
import android.util.Log
import android.util.TypedValue
import android.view.Gravity
import android.view.View
import android.view.WindowManager
import android.view.animation.DecelerateInterpolator
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
 *
 * It looks like the rest of the app and not like the television reporting an error: the same
 * surface colour, the same corner radius, the same type scale (#113). A band of system grey
 * across the top of a film reads as a fault, and a child learns to ignore faults.
 *
 * It arrives and leaves with a short slide and a fade, easing out rather than linear. A thing
 * that simply exists is a thing the eye slides off, and a thing that vanishes between frames
 * reads as a glitch — but nothing flashes, nothing bounces, and nothing asks for a press. The
 * whole job is to be noticed without stopping the programme.
 *
 * Top right rather than across the middle of a face, and the corner the platform's own toasts
 * and picture-in-picture use. It stays there: this set's image-sticking protection drifts the
 * lock screen (#50), and twelve seconds is far too short for a banner to need the same.
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
            setTextColor(TvStyle.TEXT)
            background = GradientDrawable().apply {
                cornerRadius = CORNER_PX
                setColor(SURFACE_COLOR)
            }
            setTextSize(TypedValue.COMPLEX_UNIT_SP, TvStyle.BODY_SP)
            gravity = Gravity.CENTER
            setPadding(PADDING_PX, PADDING_PX / 2, PADDING_PX, PADDING_PX / 2)
        }

        val added = runCatching { windowManager.addView(banner, layoutParams()) }
        if (added.isFailure) {
            Log.e(EnforcerService.TAG, "addView() failed for the warning", added.exceptionOrNull())
            return
        }
        root = banner
        enter(banner)
        restartTimer()
        Log.i(EnforcerService.TAG, "warning shown: $message")
    }

    /**
     * Down and in, easing out.
     *
     * Started from the first layout pass rather than immediately: a view that has not been
     * measured has no height to slide by, so the offset would be zero and the banner would only
     * fade — which is the half of the movement that is easiest to miss.
     */
    private fun enter(banner: View) {
        banner.alpha = 0f
        banner.post {
            banner.translationY = -banner.height.toFloat()
            banner.animate()
                .alpha(1f)
                .translationY(0f)
                .setDuration(ENTER_MS)
                .setInterpolator(DecelerateInterpolator())
                .start()
        }
    }

    /**
     * Leaves the way it came, then takes itself off the window.
     *
     * The view is let go of before the animation ends, so a banner already on its way out cannot
     * be handed back by [isShowing] — and a new message that arrives mid-exit builds a fresh one
     * rather than reviving the one that is fading.
     */
    fun hide() {
        handler.removeCallbacks(dismiss)
        val view = root ?: return
        root = null
        view.animate()
            .alpha(0f)
            .translationY(-view.height.toFloat())
            .setDuration(LEAVE_MS)
            .setInterpolator(DecelerateInterpolator())
            .withEndAction { remove(view) }
            .start()
    }

    private fun remove(view: View) {
        runCatching { windowManager.removeViewImmediate(view) }
            .onFailure { Log.w(EnforcerService.TAG, "removeView() failed for the warning", it) }
    }

    private fun restartTimer() {
        handler.removeCallbacks(dismiss)
        handler.postDelayed(dismiss, VISIBLE_MS)
    }

    private fun layoutParams() = WindowManager.LayoutParams(
        WindowManager.LayoutParams.WRAP_CONTENT,
        WindowManager.LayoutParams.WRAP_CONTENT,
        WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
        // The opposite choice from the lock, and for the opposite reason: this one must not
        // take focus or touches, so the remote keeps working while it is up.
        WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or
            WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE or
            WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN,
        PixelFormat.TRANSLUCENT,
    ).apply {
        gravity = Gravity.TOP or Gravity.END
        // Overscan is real on some sets, so it does not sit against the very edge.
        y = TvStyle.OVERSCAN_PX
        x = TvStyle.OVERSCAN_PX
    }

    private companion object {
        const val VISIBLE_MS = 12_000L
        const val PADDING_PX = 44
        const val CORNER_PX = 28f

        /** Long enough to be seen arriving, short enough not to be a thing that happens to you. */
        const val ENTER_MS = 320L
        const val LEAVE_MS = 240L

        // The app's own surface colour, nearly opaque rather than fully: this sits over whatever
        // is playing, and the picture showing faintly through is what keeps it a message on top
        // of a programme rather than a hole cut in one.
        const val SURFACE_COLOR = 0xF2141F2B.toInt()
    }
}
