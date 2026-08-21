/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.tv

import android.content.Context
import android.util.Log
import app.tvsitter.rules.contract.Command
import app.tvsitter.rules.contract.StateSnapshot
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch

/**
 * Owns when state goes out, and nothing about what it contains.
 *
 * The seam is deliberate: [EnforcerService] knows what the current state *is*, this knows how
 * and when it reaches the broker. Splitting them keeps the service about enforcement, which is
 * the part that has to be easy to reason about.
 */
class Telemetry(
    private val context: Context,
    private val scope: CoroutineScope,
    private val snapshot: () -> StateSnapshot,
    private val onCommand: (Command) -> Unit,
) {
    private var bridge: MqttBridge? = null
    private var pendingPublish: Job? = null
    private var heartbeatJob: Job? = null

    val isConfigured: Boolean get() = bridge != null

    /** Connects if a broker is configured. Returns false when there is nothing to connect to. */
    suspend fun start(): Boolean {
        val config = Settings(context).broker.first()
        if (!config.isComplete) return false

        bridge = MqttBridge(config, onCommand).also { it.connect() }
        heartbeatJob = scope.launch { heartbeat() }
        return true
    }

    /**
     * Reconnects with whatever is now stored. Used after pairing, where the broker may be a
     * different one entirely and a connection to the old address would keep publishing where
     * nobody is listening.
     */
    fun restart() {
        scope.launch {
            stop()
            start()
        }
    }

    /**
     * Publishes shortly, coalescing a burst into one message. App changes arrive in clusters —
     * opening one app can produce several transitions within a few hundred milliseconds — and
     * a message per transition would be noise on the broker and in the recorder.
     */
    fun publishSoon() {
        pendingPublish?.cancel()
        pendingPublish = scope.launch {
            delay(PUBLISH_DEBOUNCE_MS)
            publishNow()
        }
    }

    fun stop() {
        pendingPublish?.cancel()
        pendingPublish = null
        heartbeatJob?.cancel()
        heartbeatJob = null
        bridge?.disconnect()
        bridge = null
    }

    /**
     * Republishes on a timer even when nothing changed, so `ts` stays fresh. Without it a
     * quiet television is indistinguishable from a stale retained payload.
     */
    private suspend fun heartbeat() {
        while (scope.isActive) {
            delay(HEARTBEAT_MS)
            publishNow()
        }
    }

    private fun publishNow() {
        val active = bridge ?: return
        runCatching { active.publish(snapshot()) }
            .onFailure { Log.w(EnforcerService.TAG, "telemetry: publish failed", it) }
    }

    private companion object {
        const val PUBLISH_DEBOUNCE_MS = 400L
        const val HEARTBEAT_MS = 60_000L
    }
}
