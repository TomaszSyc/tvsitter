/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.tv

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Intent
import android.content.pm.ServiceInfo
import android.graphics.Color
import android.graphics.PixelFormat
import android.os.IBinder
import android.util.Log
import android.util.TypedValue
import android.view.Gravity
import android.view.View
import android.view.WindowManager
import android.widget.FrameLayout
import android.widget.TextView

/**
 * Spike for #20: can the lock be drawn with `SYSTEM_ALERT_WINDOW` instead of an
 * accessibility overlay, so that no accessibility service has to be enabled at all?
 *
 * Debug builds only. It exists to answer three questions on real hardware:
 *  1. does a `TYPE_APPLICATION_OVERLAY` window from *our* app cover full-screen video,
 *  2. does it hold up with the accessibility service switched off,
 *  3. what does it cost — because without accessibility the process needs a foreground
 *     service to stay alive, where the system revived the accessibility service for free
 *     within about 27 seconds of boot (D13).
 *
 * Question three is why this is written as a foreground service rather than something
 * throwaway: it is the shape option 2 would actually take.
 */
class SawSpikeService : Service() {

    private var overlay: View? = null

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        startForeground(NOTIFICATION_ID, buildNotification(), ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE)
        if (intent?.action == ACTION_HIDE) {
            hide()
            stopSelf()
            return START_NOT_STICKY
        }
        show(intent?.getStringExtra("reason") ?: "SAW spike")
        return START_STICKY
    }

    private fun show(reason: String) {
        if (overlay != null) return
        val windowManager = getSystemService(WindowManager::class.java) ?: return

        val container = FrameLayout(this).apply {
            setBackgroundColor(BACKDROP)
            addView(
                TextView(context).apply {
                    text = "SAW overlay — $reason"
                    setTextColor(Color.WHITE)
                    setTextSize(TypedValue.COMPLEX_UNIT_SP, 30f)
                    gravity = Gravity.CENTER
                },
                FrameLayout.LayoutParams(
                    FrameLayout.LayoutParams.MATCH_PARENT,
                    FrameLayout.LayoutParams.MATCH_PARENT,
                ),
            )
        }

        val params = WindowManager.LayoutParams(
            WindowManager.LayoutParams.MATCH_PARENT,
            WindowManager.LayoutParams.MATCH_PARENT,
            WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
            WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN or
                WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS,
            PixelFormat.TRANSLUCENT,
        )

        runCatching { windowManager.addView(container, params) }
            .onSuccess {
                overlay = container
                Log.i(EnforcerService.TAG, "saw-spike: overlay added")
            }
            .onFailure { Log.e(EnforcerService.TAG, "saw-spike: addView failed", it) }
    }

    private fun hide() {
        val view = overlay ?: return
        overlay = null
        runCatching { getSystemService(WindowManager::class.java)?.removeViewImmediate(view) }
        Log.i(EnforcerService.TAG, "saw-spike: overlay removed")
    }

    override fun onDestroy() {
        hide()
        super.onDestroy()
    }

    private fun buildNotification(): Notification {
        val manager = getSystemService(NotificationManager::class.java)
        manager?.createNotificationChannel(
            NotificationChannel(CHANNEL_ID, "TV Sitter spike", NotificationManager.IMPORTANCE_LOW),
        )
        return Notification.Builder(this, CHANNEL_ID)
            .setContentTitle("TV Sitter")
            .setContentText("SAW overlay spike")
            .setSmallIcon(R.drawable.banner)
            .build()
    }

    companion object {
        const val ACTION_HIDE = "app.tvsitter.tv.SAW_HIDE"

        private const val CHANNEL_ID = "tvsitter_spike"
        private const val NOTIFICATION_ID = 1
        private const val BACKDROP = 0xFF0B1017.toInt()
    }
}
