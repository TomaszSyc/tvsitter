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
import android.content.Context
import android.content.pm.ServiceInfo
import android.os.Build

/**
 * The notification a foreground service is obliged to show.
 *
 * Its own file because it is the least interesting thing the enforcer does and has no bearing
 * on enforcement — and because it only exists at all as a consequence of D16: an accessibility
 * service needed no notification, a foreground service does. On a television it is close to
 * invisible.
 */
object EnforcerNotification {

    private const val CHANNEL_ID = "tvsitter_enforcer"
    private const val NOTIFICATION_ID = 1

    /** Puts [service] into the foreground, using the typed overload where it exists. */
    fun attach(service: Service) {
        val notification = build(service)

        // The typed overload exists from API 29 and specialUse from 34; minSdk is 26.
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE) {
            service.startForeground(
                NOTIFICATION_ID,
                notification,
                ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE,
            )
        } else {
            service.startForeground(NOTIFICATION_ID, notification)
        }
    }

    private fun build(context: Context): Notification {
        context.getSystemService(NotificationManager::class.java)?.createNotificationChannel(
            NotificationChannel(
                CHANNEL_ID,
                context.getString(R.string.notification_channel),
                NotificationManager.IMPORTANCE_LOW,
            ),
        )
        return Notification.Builder(context, CHANNEL_ID)
            .setContentTitle(context.getString(R.string.app_name))
            .setContentText(context.getString(R.string.notification_running))
            .setSmallIcon(R.drawable.banner)
            .setOngoing(true)
            .build()
    }
}
