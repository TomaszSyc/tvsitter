/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.tv

import android.content.Context
import android.util.Log
import app.tvsitter.rules.contract.Alert
import app.tvsitter.rules.contract.Command
import app.tvsitter.rules.contract.DaySummary
import app.tvsitter.rules.contract.StateSnapshot
import app.tvsitter.rules.contract.TimeRequest
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
    /** The rules exactly as stored, asked for rather than held: they change without us. */
    private val rules: () -> String,
    private val onCommand: (Command) -> Unit,
) {
    private var bridge: MqttBridge? = null
    private var pendingPublish: Job? = null
    private var heartbeatJob: Job? = null

    /** Whether there are broker settings to work with, which is what pairing produces. */
    val isConfigured: Boolean get() = bridge != null

    /**
     * Whether the broker is reachable right now. A different question from [isConfigured]:
     * a paired TV with the broker down is configured and silent, and the setup screen has to
     * be able to tell somebody which of the two they are looking at.
     */
    val isConnected: Boolean get() = bridge?.isConnected == true

    /** Connects if a broker is configured. Returns false when there is nothing to connect to. */
    suspend fun start(): Boolean {
        val config = Settings(context).broker.first()
        if (!config.isComplete) return false

        // Assigned before connecting, not inside `also`: the connected listener publishes
        // state through `bridge`, and it can fire before `also` has finished returning.
        // Both on connect: a retained rules topic that is never written says the television is
        // enforcing nothing, which is a worse lie than saying nothing at all.
        val fresh = MqttBridge(config, onCommand, onConnected = {
            publishNow()
            publishRules(rules())
            flushAlerts()
            // Retained on the broker already, but a broker that lost its store — or a fresh
            // one after a move — would otherwise have no yesterday until tomorrow.
            scope.launch {
                Settings(context).lastDay()?.let { day -> bridge?.publishDay(day) }
            }
        })
        bridge = fresh
        fresh.connect()
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

    /**
     * Sends a request from the child straight out, with no debouncing.
     *
     * Unlike state, which is a picture that can wait a moment for the next one, a request is a
     * question — and it is only asked once, so there is nothing to coalesce it with.
     */
    fun publish(request: TimeRequest) {
        val out = bridge
        if (out == null) {
            Log.w(EnforcerService.TAG, "request ${request.id} not sent: no broker configured")
            return
        }
        out.publish(request)
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

    /** Sends the rules as they now stand, so Home Assistant can show what is being enforced. */
    fun publishRules(json: String) {
        val active = bridge ?: return
        runCatching { active.publishRules(json) }
            .onFailure { Log.w(EnforcerService.TAG, "telemetry: rules publish failed", it) }
    }

    /** Sends a day that has just closed. */
    fun publish(day: DaySummary) {
        val active = bridge ?: return
        runCatching { active.publish(day) }
            .onFailure { Log.w(EnforcerService.TAG, "telemetry: day publish failed", it) }
    }

    /**
     * Raises an alarm, or holds it until there is somewhere to raise it.
     *
     * The alarms that matter most are the ones raised at start-up, and start-up is exactly
     * when the broker is not there yet: measured, `unclean_restart` was dropped eight hundred
     * milliseconds before the connection came up (#106). An alarm is not retained on the wire,
     * so waiting here is the only place it can wait.
     *
     * Bounded, oldest dropped first. This is for the handful raised before a connection, not a
     * spool for a television that has been offline all evening — by then the alarm is history
     * and the state payload says more than it would.
     */
    fun publish(alert: Alert) {
        val sent = bridge?.let { active ->
            runCatching { active.publish(alert) }
                .onFailure { Log.w(EnforcerService.TAG, "telemetry: alert publish failed", it) }
                .getOrDefault(false)
        } ?: false
        if (sent) return

        if (waitingAlerts.size >= MAX_WAITING_ALERTS) waitingAlerts.removeFirst()
        waitingAlerts += alert
        Log.i(EnforcerService.TAG, "telemetry: holding alert ${alert.kind} until the broker is up")
    }

    /** Sends what was raised before there was anywhere to send it. */
    private fun flushAlerts() {
        if (waitingAlerts.isEmpty()) return
        val holding = waitingAlerts.toList()
        waitingAlerts.clear()
        Log.i(EnforcerService.TAG, "telemetry: sending ${holding.size} alert(s) held from start-up")
        holding.forEach { alert -> publish(alert) }
    }

    private fun publishNow() {
        val active = bridge ?: return
        runCatching { active.publish(snapshot()) }
            .onFailure { Log.w(EnforcerService.TAG, "telemetry: publish failed", it) }
    }

    private val waitingAlerts = ArrayDeque<Alert>()

    private companion object {
        const val PUBLISH_DEBOUNCE_MS = 400L

        /** Enough for a start-up's worth. An alarm from last night is history, not news. */
        const val MAX_WAITING_ALERTS = 8
        const val HEARTBEAT_MS = 60_000L
    }
}
