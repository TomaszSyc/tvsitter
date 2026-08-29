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

    /**
     * The rules in force, retained.
     *
     * The television keeps them and enforces them offline (D3), so it is the only thing that
     * knows what is actually being enforced. Without this, Home Assistant can show the daily
     * limit — because the state payload carries it — and nothing else: not the week, not the
     * hours, not one app's budget. "Why did it lock at half past seven" is unanswerable from a
     * dashboard, which is the question a schedule invites.
     */
    const val TOPIC_RULES: String = "rules"

    /**
     * The last closed budget day, retained.
     *
     * A day that ends leaves nothing behind otherwise: the counter wipes the per-app split on
     * rollover, and Home Assistant only knows what it was told while it was listening. One day
     * only — the archive is the recorder's job, not the television's.
     */
    const val TOPIC_DAY: String = "day"
    const val TOPIC_COMMAND: String = "cmd"

    const val PAYLOAD_ONLINE: String = "online"
    const val PAYLOAD_OFFLINE: String = "offline"

    /**
     * Values for `pin_changed_by`. Where a PIN was last changed is the only thing that makes
     * the timestamp actionable: a change made in Home Assistant was made by somebody holding
     * the parent's phone, and one made on the television by whoever was in the room.
     */
    const val PIN_SOURCE_TV: String = "tv"
    const val PIN_SOURCE_HA: String = "ha"
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
    val rules: String get() = "$prefix/${Contract.TOPIC_RULES}"
    val day: String get() = "$prefix/${Contract.TOPIC_DAY}"
    val command: String get() = "$prefix/${Contract.TOPIC_COMMAND}"

    override fun equals(other: Any?): Boolean = other is Topics && other.prefix == prefix

    override fun hashCode(): Int = prefix.hashCode()

    override fun toString(): String = "Topics($prefix)"
}
