/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.tv

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.util.Log
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch

/**
 * Drives the M0 spike from ADB. The component must be addressed explicitly, because a
 * manifest-declared receiver has not received implicit broadcasts since Android 8 — without
 * `-n` the broadcast reports success and runs nothing:
 *
 *   R=app.tvsitter.tv/.DebugCommandReceiver
 *   adb shell am broadcast -n $R -a app.tvsitter.tv.LOCK --es reason "lock test"
 *   adb shell am broadcast -n $R -a app.tvsitter.tv.UNLOCK
 *   adb shell am broadcast -n $R -a app.tvsitter.tv.STATUS
 *   adb shell am broadcast -n $R -a app.tvsitter.tv.CONFIGURE --es host 192.168.1.10 ...
 *
 * CONFIGURE exists because typing a broker password with a TV remote is punishment. It
 * passes the password as a broadcast extra, which lands in the system log — acceptable for
 * a development build, and a reason this receiver is absent from release builds.
 */
class DebugCommandReceiver : BroadcastReceiver() {

    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action == ACTION_CONFIGURE) {
            configure(context, intent)
            return
        }

        // The SAW spike deliberately does not go through the accessibility service: the
        // whole point is that it has to work with that service switched off.
        if (intent.action == ACTION_SAW_LOCK || intent.action == ACTION_SAW_UNLOCK) {
            val service = Intent(context, SawSpikeService::class.java).apply {
                if (intent.action == ACTION_SAW_UNLOCK) action = SawSpikeService.ACTION_HIDE
                intent.getStringExtra("reason")?.let { putExtra("reason", it) }
            }
            context.startForegroundService(service)
            return
        }

        val service = EnforcerService.instance
        if (service == null) {
            Log.w(EnforcerService.TAG, "${intent.action}: accessibility service is not connected")
            return
        }
        when (intent.action) {
            ACTION_LOCK -> service.lock(intent.getStringExtra("reason") ?: "lock test from ADB")
            ACTION_UNLOCK -> service.unlock()
            ACTION_STATUS -> Log.i(
                EnforcerService.TAG,
                "STATUS: locked=${service.isLocked} foreground=${service.foregroundPackage}",
            )
            else -> Log.w(EnforcerService.TAG, "unknown action: ${intent.action}")
        }
    }

    /**
     * Writes broker settings and restarts the connection. Only the extras present are
     * touched, so a single value can be corrected without re-entering the rest.
     */
    private fun configure(context: Context, intent: Intent) {
        val pending = goAsync()
        val settings = Settings(context.applicationContext)
        CoroutineScope(Dispatchers.IO).launch {
            try {
                settings.updateBroker { current ->
                    current.copy(
                        host = intent.getStringExtra("host") ?: current.host,
                        port = intent.getStringExtra("port")?.toIntOrNull() ?: current.port,
                        username = intent.getStringExtra("user") ?: current.username,
                        password = intent.getStringExtra("pass") ?: current.password,
                        topicPrefix = intent.getStringExtra("prefix") ?: current.topicPrefix,
                        useTls = intent.getStringExtra("tls")?.toBooleanStrictOrNull() ?: current.useTls,
                    )
                }
                val stored = settings.brokerSnapshot()
                Log.i(
                    EnforcerService.TAG,
                    "configured: host=${stored.host}:${stored.port} prefix=${stored.topicPrefix} " +
                        "user=${stored.username.ifBlank { "(none)" }} tls=${stored.useTls} " +
                        "password=${if (stored.password.isBlank()) "(none)" else "(set)"}",
                )
                EnforcerService.instance?.reconnectMqtt()
            } finally {
                pending.finish()
            }
        }
    }

    private companion object {
        const val ACTION_LOCK = "app.tvsitter.tv.LOCK"
        const val ACTION_UNLOCK = "app.tvsitter.tv.UNLOCK"
        const val ACTION_STATUS = "app.tvsitter.tv.STATUS"
        const val ACTION_CONFIGURE = "app.tvsitter.tv.CONFIGURE"
        const val ACTION_SAW_LOCK = "app.tvsitter.tv.SAW_LOCK"
        const val ACTION_SAW_UNLOCK = "app.tvsitter.tv.SAW_UNLOCK"
    }
}
