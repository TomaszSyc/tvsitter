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
    private var root: FrameLayout? = null
    private var face: LinearLayout? = null
    private var subtitleView: TextView? = null
    private var askButton: Button? = null
    private var pinButton: Button? = null
    private var keypad: PinKeypad? = null

    /** Held in a field so a later [show] can replace it without leaving a stale one wired up. */
    private var onEnterPin: (() -> Unit)? = null

    val isShowing: Boolean
        get() = root != null

    /**
     * Puts the lock up, or updates what it says if it is already up.
     *
     * [onEnterPin] is null when this television has no parent PIN, and then there is no button
     * for one. Offering a keypad with nothing behind it would be an invitation to guess at
     * something that does not exist.
     */
    fun show(title: String, subtitle: String?, onAskForTime: () -> Unit, onEnterPin: (() -> Unit)?) {
        this.onEnterPin = onEnterPin
        if (root != null) {
            subtitleView?.applySubtitle(subtitle)
            // A PIN can arrive from Home Assistant while the lock is already up, and the way
            // out of the lock should not have to wait for the next time it is raised.
            pinButton?.visibility = if (onEnterPin != null) View.VISIBLE else View.GONE
            return
        }

        val column = buildFace(title, subtitle, onAskForTime, onEnterPin != null)
        val container = FrameLayout(context).apply {
            setBackgroundColor(BACKDROP_COLOR)
            // The container must not be focusable itself. Made focusable, it wins focus and
            // then swallows every D-pad and ENTER event instead of letting them reach the
            // button — which on a TV means the lock screen's own controls are dead.
            isFocusable = false
            descendantFocusability = FrameLayout.FOCUS_AFTER_DESCENDANTS
            addView(column, centred())
        }

        val added = runCatching { windowManager.addView(container, layoutParams()) }
        if (added.isFailure) {
            Log.e(EnforcerService.TAG, "addView() failed for the overlay", added.exceptionOrNull())
            return
        }
        root = container
        face = column
        askButton?.requestFocus()
        Log.i(
            EnforcerService.TAG,
            "overlay shown: $title / $subtitle, pin=${onEnterPin != null}, " +
                "button focused=${askButton?.isFocused}",
        )
    }

    fun hide() {
        val view = root ?: return
        runCatching { windowManager.removeViewImmediate(view) }
            .onFailure { Log.e(EnforcerService.TAG, "removeView() failed", it) }
        root = null
        face = null
        subtitleView = null
        askButton = null
        pinButton = null
        keypad = null
        Log.i(EnforcerService.TAG, "overlay removed")
    }

    /**
     * Swaps the lock face for a keypad, inside the same window.
     *
     * The window stays up throughout on purpose: taking it down to show a keypad would give
     * whoever is in the room a few frames of unlocked television, and put it back if the PIN
     * turned out to be wrong.
     *
     * [onSubmit] returns the message to show, or null when the PIN was right — in which case
     * the lock is on its way down and there is nothing left to say.
     */
    fun showKeypad(prompt: String, onSubmit: (String) -> String?) {
        val container = root ?: return
        if (keypad != null) return

        val pad = PinKeypad(
            context,
            onSubmit = { typed -> onSubmit(typed)?.let { message -> keypad?.message(message) } },
            onCancel = { hideKeypad() },
        )
        keypad = pad
        face?.visibility = View.GONE
        container.addView(pad, centred())
        pad.prompt(prompt)
        pad.focusKeypad()
        Log.i(EnforcerService.TAG, "overlay: keypad up")
    }

    /** Says something on a keypad that is already up, for an answer that took a while. */
    fun keypadMessage(text: String) {
        keypad?.message(text)
    }

    private fun hideKeypad() {
        val pad = keypad ?: return
        keypad = null
        root?.removeView(pad)
        face?.visibility = View.VISIBLE
        askButton?.requestFocus()
        Log.i(EnforcerService.TAG, "overlay: keypad dismissed")
    }

    private fun buildFace(title: String, subtitle: String?, onAskForTime: () -> Unit, withPin: Boolean): LinearLayout {
        askButton = Button(context).apply {
            text = context.getString(R.string.lock_ask_more)
            isFocusable = true
            isFocusableInTouchMode = true
            setOnClickListener { onAskForTime() }
        }
        pinButton = Button(context).apply {
            text = context.getString(R.string.pin_unlock)
            isFocusable = true
            setOnClickListener { this@LockOverlay.onEnterPin?.invoke() }
            visibility = if (withPin) View.VISIBLE else View.GONE
        }

        return LinearLayout(context).apply {
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
            addView(pinButton)
        }
    }

    private fun centred() = FrameLayout.LayoutParams(
        FrameLayout.LayoutParams.WRAP_CONTENT,
        FrameLayout.LayoutParams.WRAP_CONTENT,
        Gravity.CENTER,
    )

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
