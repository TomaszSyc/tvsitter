/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.tv

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.hardware.display.DisplayManager
import android.util.Log
import android.view.Display

/**
 * Tracks whether the panel is actually showing anything.
 *
 * This is not the same question as "is the app in the foreground". A Google TV in standby
 * keeps the system running, so our service stays alive and connected with the screen off —
 * which is exactly the signal Home Assistant needs to tell "TV off" apart from "app
 * crashed". Time must not accrue while the screen is off.
 *
 * `ACTION_SCREEN_ON` and `ACTION_SCREEN_OFF` cannot be declared in a manifest; they are
 * only delivered to receivers registered at runtime.
 */
class ScreenState(private val context: Context, private val onChanged: (Boolean) -> Unit) {
    @Volatile
    var isScreenOn: Boolean = false
        private set

    private val receiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context, intent: Intent) {
            when (intent.action) {
                Intent.ACTION_SCREEN_ON -> update(true)
                Intent.ACTION_SCREEN_OFF -> update(false)
            }
        }
    }

    fun start() {
        isScreenOn = readFromDisplays()
        Log.i(EnforcerService.TAG, "screen state at start: on=$isScreenOn")
        context.registerReceiver(
            receiver,
            IntentFilter().apply {
                addAction(Intent.ACTION_SCREEN_ON)
                addAction(Intent.ACTION_SCREEN_OFF)
            },
        )
    }

    fun stop() {
        runCatching { context.unregisterReceiver(receiver) }
            .onFailure { Log.w(EnforcerService.TAG, "unregisterReceiver failed", it) }
    }

    private fun update(on: Boolean) {
        if (on == isScreenOn) return
        isScreenOn = on
        Log.i(EnforcerService.TAG, "screen ${if (on) "on" else "off"}")
        onChanged(on)
    }

    /**
     * The broadcasts only report changes, so the initial value has to come from somewhere
     * else. A display in [Display.STATE_ON] counts; dozing and standby do not.
     */
    private fun readFromDisplays(): Boolean {
        val displayManager = context.getSystemService(DisplayManager::class.java) ?: return true
        return displayManager.displays.any { it.state == Display.STATE_ON }
    }
}
