/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.tv

import android.accessibilityservice.AccessibilityService
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
 * [WindowManager.LayoutParams.TYPE_ACCESSIBILITY_OVERLAY] window: it needs no
 * SYSTEM_ALERT_WINDOW permission and sits in a window layer above ordinary system alerts.
 *
 * Deliberately built from plain views rather than Compose: an accessibility window has
 * none of the lifecycle owners Compose expects, and this class is load-bearing for the
 * whole product — the less machinery here, the fewer ways it can break.
 */
class LockOverlay(private val service: AccessibilityService) {

    private val windowManager = service.getSystemService(WindowManager::class.java)
    private var root: View? = null
    private var subtitleView: TextView? = null

    val isShowing: Boolean
        get() = root != null

    fun show(title: String, subtitle: String, onAskForTime: () -> Unit) {
        if (root != null) {
            subtitleView?.text = subtitle
            return
        }

        val askButton = Button(service).apply {
            text = service.getString(R.string.lock_ask_more)
            isFocusable = true
            isFocusableInTouchMode = true
            setOnClickListener { onAskForTime() }
        }

        val column = LinearLayout(service).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER_HORIZONTAL
            addView(textView(title, sizeSp = 34f, color = Color.WHITE))
            addView(textView(subtitle, sizeSp = 18f, color = SUBTITLE_COLOR).also { subtitleView = it })
            addView(askButton)
        }

        val container = FrameLayout(service).apply {
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

    /** Re-inserts the window when another app window has appeared above the lock. */
    fun reassert() {
        val view = root ?: return
        runCatching { windowManager.removeViewImmediate(view) }
        val readded = runCatching { windowManager.addView(view, layoutParams()) }
        if (readded.isFailure) {
            Log.e(EnforcerService.TAG, "reassert() failed — the lock may be gone", readded.exceptionOrNull())
            root = null
        } else {
            view.findFocus() ?: view.requestFocus()
            Log.i(EnforcerService.TAG, "overlay reasserted above a new window")
        }
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
        WindowManager.LayoutParams.TYPE_ACCESSIBILITY_OVERLAY,
        // Omitting FLAG_NOT_FOCUSABLE is intentional: the window must receive D-pad input.
        WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN or
            WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS,
        PixelFormat.TRANSLUCENT,
    )

    private fun textView(value: String, sizeSp: Float, color: Int) = TextView(service).apply {
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
