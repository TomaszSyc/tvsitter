/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.rules.contract

/**
 * The MQTT contract, as described in `docs/mqtt-contract.md`.
 *
 * It lives in `:rules` rather than in the Android module so that the app and anything else
 * speaking this protocol share one definition, and so that it can be tested on the JVM.
 */
object Contract {
    /**
     * Payload schema version. Bump this when a field changes meaning or disappears, never
     * when one is merely added — additions are handled by ignoring unknown keys.
     */
    const val SCHEMA_VERSION: Int = 1

    const val TOPIC_AVAILABILITY: String = "availability"
    const val TOPIC_STATE: String = "state"
    const val TOPIC_REQUEST: String = "request"
    const val TOPIC_COMMAND: String = "cmd"

    const val PAYLOAD_ONLINE: String = "online"
    const val PAYLOAD_OFFLINE: String = "offline"
}

/**
 * The four topics for one device, derived from a prefix such as `tvsitter/livingroom`.
 *
 * Wildcards are rejected rather than escaped: a `+` or `#` in the prefix would mean
 * subscribing to other devices' topics and publishing commands into unknown places.
 */
class Topics(prefix: String) {
    val prefix: String = prefix.trim().trim('/').also {
        require(it.isNotEmpty()) { "topic prefix must not be empty" }
        require(!it.contains('+') && !it.contains('#')) {
            "topic prefix must not contain MQTT wildcards, was '$it'"
        }
    }

    val availability: String get() = "$prefix/${Contract.TOPIC_AVAILABILITY}"
    val state: String get() = "$prefix/${Contract.TOPIC_STATE}"
    val request: String get() = "$prefix/${Contract.TOPIC_REQUEST}"
    val command: String get() = "$prefix/${Contract.TOPIC_COMMAND}"

    override fun equals(other: Any?): Boolean = other is Topics && other.prefix == prefix

    override fun hashCode(): Int = prefix.hashCode()

    override fun toString(): String = "Topics($prefix)"
}
