/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.tv

import android.util.Log
import app.tvsitter.rules.contract.Command
import app.tvsitter.rules.contract.Contract
import app.tvsitter.rules.contract.ContractCodec
import app.tvsitter.rules.contract.StateSnapshot
import app.tvsitter.rules.contract.TimeRequest
import app.tvsitter.rules.contract.Topics
import com.hivemq.client.mqtt.MqttClient
import com.hivemq.client.mqtt.datatypes.MqttQos
import com.hivemq.client.mqtt.lifecycle.MqttClientDisconnectedContext
import com.hivemq.client.mqtt.mqtt5.Mqtt5AsyncClient
import com.hivemq.client.mqtt.mqtt5.lifecycle.Mqtt5ClientDisconnectedContext
import com.hivemq.client.mqtt.mqtt5.message.connect.Mqtt5Connect
import java.util.concurrent.TimeUnit

/**
 * The only thing that talks to the broker.
 *
 * The three rules from `docs/mqtt-contract.md` are enforced here rather than left to
 * callers, because getting any of them wrong is silent: availability is the Last Will, so a
 * crashed app cannot look alive; `state` is retained, so Home Assistant knows the state
 * straight after a restart; commands are never published from this side at all.
 */
class MqttBridge(
    private val config: BrokerConfig,
    private val onCommand: (Command) -> Unit,
    private val onConnected: () -> Unit = {},
) {
    private val topics = Topics(config.topicPrefix)
    private var client: Mqtt5AsyncClient? = null

    val isConnected: Boolean
        get() = client?.state?.isConnected == true

    /**
     * Built once and used for every attempt, first and reconnects alike.
     *
     * Credentials, the will, `cleanStart` and `keepAlive` are all CONNECT fields, and
     * HiveMQ's automatic reconnect does not reuse the message given to `connectWith()` — it
     * builds a default one. The broker therefore saw a CONNECT with no username on every
     * retry and refused it, which is hivemq/hivemq-mqtt-client#574 and is why this TV sat
     * for twelve hours retrying against `not authorised`. Neither `cleanStart` nor
     * `keepAlive` can be set on the client builder either, so keeping one Connect and
     * handing it to both the first attempt and the reconnector is what makes the attempts
     * identical.
     */
    private val connectMessage: Mqtt5Connect = buildConnectMessage()

    private fun buildConnectMessage(): Mqtt5Connect {
        var builder = Mqtt5Connect.builder()
            .cleanStart(true)
            .keepAlive(KEEP_ALIVE_S)

        // Carried, not discarded: these builders return a new instance rather than mutating,
        // and dropping the result is how TLS came to be silently disabled once already.
        if (config.username.isNotBlank()) {
            builder = builder.simpleAuth()
                .username(config.username)
                .password(config.password.toByteArray())
                .applySimpleAuth()
        }

        return builder
            .willPublish()
            .topic(topics.availability)
            .payload(Contract.PAYLOAD_OFFLINE.toByteArray())
            .qos(MqttQos.AT_LEAST_ONCE)
            .retain(true)
            .applyWillPublish()
            .build()
    }

    fun connect() {
        if (client != null) {
            Log.w(EnforcerService.TAG, "mqtt: connect() called twice, ignoring")
            return
        }

        val base = MqttClient.builder()
            .useMqttVersion5()
            .identifier("tvsitter-${topics.prefix.replace('/', '-')}")
            .serverHost(config.host)
            .serverPort(config.port)
            // Announcing availability and resubscribing belong to a connection, not to the
            // client, so they hang off the connected listener. Doing them in the connect
            // callback meant that after the first dropped connection Home Assistant kept
            // seeing the Last Will, and commands were accepted by the broker and silently
            // ignored by us.
            .addConnectedListener { onConnectionUp() }
            .addDisconnectedListener(::onConnectionDown)
            // This TV drops off the network in standby, so reconnecting is the normal case
            // rather than an error path. Backoff caps at a minute: a locked TV that cannot
            // reach the broker still enforces locally, so there is nothing to rush for.
            .automaticReconnect()
            .initialDelay(1, TimeUnit.SECONDS)
            .maxDelay(RECONNECT_MAX_DELAY_S, TimeUnit.SECONDS)
            .applyAutomaticReconnect()

        // The builder is immutable: sslWithDefaultConfig() returns a new one rather than
        // mutating this one, so its result has to be carried forward. Discarding it — which
        // an earlier version did inside an apply block — meant TLS silently did nothing.
        val built = (if (config.useTls) base.sslWithDefaultConfig() else base).buildAsync()
        client = built

        built.connect(connectMessage)
            .whenComplete { _, error ->
                // Success is handled by the connected listener, which also covers reconnects.
                if (error != null) {
                    Log.e(EnforcerService.TAG, "mqtt: connect to ${config.host} failed", error)
                }
            }
    }

    private fun onConnectionUp() {
        Log.i(EnforcerService.TAG, "mqtt: connected to ${config.host}, prefix ${topics.prefix}")
        announceOnline()
        subscribeToCommands()
        // Without this the retained snapshot stays stale until the next heartbeat, which is a
        // minute of Home Assistant showing what the TV was doing before it dropped off.
        onConnected()
    }

    /**
     * The only record that a connection was lost.
     *
     * There was none before, which is why a twelve-hour outage left nothing to read: the app
     * was running, the entities were unavailable, and no log line said either had happened.
     * `reconnect` says whether another attempt is coming; false means it has given up, which
     * is the state worth noticing.
     */
    private fun onConnectionDown(context: MqttClientDisconnectedContext) {
        Log.w(
            EnforcerService.TAG,
            "mqtt: disconnected by ${context.source}, attempt ${context.reconnector.attempts}, " +
                "reconnect=${context.reconnector.isReconnect}",
            context.cause,
        )
        // Left to itself the reconnector sends a default CONNECT, without our credentials or
        // will. Handing it the same message the first attempt used is the whole fix.
        //
        // resubscribeIfSessionExpired is off because the connected listener subscribes on
        // every connection. With both, the filter was subscribed twice and every command
        // arrived twice — which for a `grant` would have handed out double the minutes.
        (context as? Mqtt5ClientDisconnectedContext)?.reconnector
            ?.connect(connectMessage)
            ?.resubscribeIfSessionExpired(false)
    }

    fun publish(snapshot: StateSnapshot) {
        // Quietly skipped while disconnected rather than attempted and warned about. State is
        // republished on a heartbeat anyway, and a retained topic means nothing is lost — but
        // a warning at startup, before the connection is up, reads like the cause of whatever
        // someone is actually debugging.
        val active = client?.takeIf { it.state.isConnected } ?: return
        active.publishWith()
            .topic(topics.state)
            .payload(ContractCodec.encode(snapshot).toByteArray())
            .qos(MqttQos.AT_MOST_ONCE)
            .retain(true)
            .send()
            .whenComplete { _, error ->
                if (error != null) Log.w(EnforcerService.TAG, "mqtt: state publish failed", error)
            }
    }

    fun publish(request: TimeRequest) {
        // A request is different: it must not be silently dropped, because a child pressed a
        // button and is waiting for an answer. Logged loudly so the failure is visible.
        val active = client?.takeIf { it.state.isConnected }
        if (active == null) {
            Log.w(EnforcerService.TAG, "mqtt: not connected, time request could not be sent")
            return
        }
        active.publishWith()
            .topic(topics.request)
            .payload(ContractCodec.encode(request).toByteArray())
            .qos(MqttQos.AT_LEAST_ONCE)
            // Deliberately not retained: a retained request would be answered again after
            // every broker restart, granting time nobody asked for.
            .retain(false)
            .send()
            .whenComplete { _, error ->
                if (error != null) Log.w(EnforcerService.TAG, "mqtt: request publish failed", error)
            }
    }

    fun disconnect() {
        val active = client ?: return
        client = null
        // Publishing "offline" before a deliberate disconnect: the Last Will only fires when
        // the connection drops unexpectedly.
        active.publishWith()
            .topic(topics.availability)
            .payload(Contract.PAYLOAD_OFFLINE.toByteArray())
            .qos(MqttQos.AT_LEAST_ONCE)
            .retain(true)
            .send()
            .whenComplete { _, _ -> active.disconnect() }
    }

    private fun announceOnline() {
        client?.publishWith()
            ?.topic(topics.availability)
            ?.payload(Contract.PAYLOAD_ONLINE.toByteArray())
            ?.qos(MqttQos.AT_LEAST_ONCE)
            ?.retain(true)
            ?.send()
    }

    private fun subscribeToCommands() {
        client?.subscribeWith()
            ?.topicFilter(topics.command)
            ?.qos(MqttQos.AT_LEAST_ONCE)
            ?.callback { publish ->
                val payload = String(publish.payloadAsBytes)
                runCatching { ContractCodec.decodeCommand(payload) }
                    .onSuccess { command ->
                        Log.i(EnforcerService.TAG, "mqtt: command $command")
                        onCommand(command)
                    }
                    .onFailure { Log.w(EnforcerService.TAG, "mqtt: undecodable command: $payload", it) }
            }
            ?.send()
            ?.whenComplete { _, error ->
                if (error != null) {
                    Log.e(EnforcerService.TAG, "mqtt: subscribe to ${topics.command} failed", error)
                } else {
                    Log.i(EnforcerService.TAG, "mqtt: subscribed to ${topics.command}")
                }
            }
    }

    private companion object {
        const val KEEP_ALIVE_S = 30
        const val RECONNECT_MAX_DELAY_S = 60L
    }
}
