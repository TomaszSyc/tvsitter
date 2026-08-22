/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.tv

import android.content.Context
import android.graphics.Color
import android.graphics.PixelFormat
import android.util.Log
import android.util.TypedValue
import android.view.Gravity
import android.view.View
import android.view.WindowManager
import android.widget.Button
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.TextView

/**
 * Full-screen lock screen drawn as a
 * [WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY] window, which needs the
 * `SYSTEM_ALERT_WINDOW` app-op — granted over ADB during setup, as D16 explains.
 *
 * That window type sits at layer 111000, above every application window including the
 * launcher, which is why there is no longer anything to re-assert: pressing HOME changes what
 * is *behind* the lock and nothing more. The previous accessibility overlay had to be removed
 * and re-added whenever a new window appeared above it.
 *
 * Deliberately built from plain views rather than Compose: this class is load-bearing for the
 * whole product, and the less machinery here, the fewer ways it can break.
 */
class LockOverlay(private val context: Context) {

    private val windowManager = context.getSystemService(WindowManager::class.java)
    private var root: View? = null
    private var subtitleView: TextView? = null

    val isShowing: Boolean
        get() = root != null

    fun show(title: String, subtitle: String?, onAskForTime: () -> Unit) {
        if (root != null) {
            subtitleView?.applySubtitle(subtitle)
            return
        }

        val askButton = Button(context).apply {
            text = context.getString(R.string.lock_ask_more)
            isFocusable = true
            isFocusableInTouchMode = true
            setOnClickListener { onAskForTime() }
        }

        val column = LinearLayout(context).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER_HORIZONTAL
            addView(textView(title, sizeSp = 34f, color = Color.WHITE))
            addView(
                textView(subtitle.orEmpty(), sizeSp = 18f, color = SUBTITLE_COLOR).also {
                    subtitleView = it
                    it.applySubtitle(subtitle)
                },
            )
            addView(askButton)
        }

        val container = FrameLayout(context).apply {
            setBackgroundColor(BACKDROP_COLOR)
            // The container must not be focusable itself. Made focusable, it wins focus and
            // then swallows every D-pad and ENTER event instead of letting them reach the
            // button — which on a TV means the lock screen's own controls are dead.
            isFocusable = false
            descendantFocusability = FrameLayout.FOCUS_AFTER_DESCENDANTS
            addView(
                column,
                FrameLayout.LayoutParams(
                    FrameLayout.LayoutParams.WRAP_CONTENT,
                    FrameLayout.LayoutParams.WRAP_CONTENT,
                    Gravity.CENTER,
                ),
            )
        }

        val added = runCatching { windowManager.addView(container, layoutParams()) }
        if (added.isFailure) {
            Log.e(EnforcerService.TAG, "addView() failed for the overlay", added.exceptionOrNull())
            return
        }
        root = container
        askButton.requestFocus()
        Log.i(
            EnforcerService.TAG,
            "overlay shown: $title / $subtitle, button focused=${askButton.isFocused}",
        )
    }

    fun hide() {
        val view = root ?: return
        runCatching { windowManager.removeViewImmediate(view) }
            .onFailure { Log.e(EnforcerService.TAG, "removeView() failed", it) }
        root = null
        subtitleView = null
        Log.i(EnforcerService.TAG, "overlay removed")
    }

    private fun layoutParams() = WindowManager.LayoutParams(
        WindowManager.LayoutParams.MATCH_PARENT,
        WindowManager.LayoutParams.MATCH_PARENT,
        WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
        // Omitting FLAG_NOT_FOCUSABLE is intentional, and load-bearing: without focus the
        // D-pad reaches the app underneath and a child can navigate it blind behind the lock.
        WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN or
            WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS,
        PixelFormat.TRANSLUCENT,
    )

    /** Blank means there is nothing to say, which is different from saying nothing. */
    private fun TextView.applySubtitle(subtitle: String?) {
        text = subtitle.orEmpty()
        visibility = if (subtitle.isNullOrBlank()) View.GONE else View.VISIBLE
    }

    private fun textView(value: String, sizeSp: Float, color: Int) = TextView(context).apply {
        text = value
        setTextColor(color)
        setTextSize(TypedValue.COMPLEX_UNIT_SP, sizeSp)
        gravity = Gravity.CENTER
        setPadding(0, 0, 0, PADDING_PX)
    }

    private companion object {
        // Fully opaque, deliberately. An earlier 95% alpha looked nicer and let a bright
        // picture show through on a large panel, which defeats the point of a lock.
        const val BACKDROP_COLOR = 0xFF0B1017.toInt()
        const val SUBTITLE_COLOR = 0xFFB9C6D2.toInt()
        const val PADDING_PX = 24
    }
}
