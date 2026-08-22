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
import android.os.UserManager
import android.util.Log

/**
 * Holds back anything that needs credential-encrypted storage until there is any.
 *
 * The service can now start before the user is unlocked (D22), and at that point the broker
 * settings, the rules and the counter are all unreadable. Reading them anyway is not a
 * recoverable error — it is a service that starts, fails and leaves nothing enforcing — so the
 * work is deferred rather than attempted and caught.
 *
 * On an ordinary start the gate is already open and the block runs immediately, which is the
 * usual case and costs nothing.
 */
class UnlockGate(private val context: Context) {

    private var receiver: BroadcastReceiver? = null

    /** Whether credential-encrypted storage can be read. */
    val isOpen: Boolean
        get() = context.getSystemService(UserManager::class.java)?.isUserUnlocked != false

    fun whenOpen(block: () -> Unit) {
        if (isOpen) {
            block()
            return
        }

        Log.i(EnforcerService.TAG, "storage locked; deferring startup until the user unlocks")
        val listener = object : BroadcastReceiver() {
            override fun onReceive(context: Context, intent: Intent) {
                if (intent.action != Intent.ACTION_USER_UNLOCKED) return
                Log.i(EnforcerService.TAG, "user unlocked; finishing startup")
                stop()
                block()
            }
        }
        receiver = listener
        context.registerReceiver(listener, IntentFilter(Intent.ACTION_USER_UNLOCKED))
    }

    fun stop() {
        val listener = receiver ?: return
        receiver = null
        runCatching { context.unregisterReceiver(listener) }
            .onFailure { Log.w(EnforcerService.TAG, "unregisterReceiver failed", it) }
    }
}
