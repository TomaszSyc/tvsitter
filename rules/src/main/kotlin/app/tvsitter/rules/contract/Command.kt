/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.rules.contract

import kotlinx.serialization.ExperimentalSerializationApi
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonClassDiscriminator
import kotlinx.serialization.json.JsonObject

/**
 * What Home Assistant sends on `<prefix>/cmd`. Never retained — a retained lock would come
 * back on its own after every broker or TV restart, for no reason anybody could explain.
 */
@OptIn(ExperimentalSerializationApi::class)
@Serializable
@JsonClassDiscriminator("op")
sealed interface Command {
    @Serializable
    @SerialName("lock")
    data class Lock(val reason: String? = null) : Command

    /** [minutes] null means "until the end of the budget day". */
    @Serializable
    @SerialName("unlock")
    data class Unlock(val minutes: Int? = null) : Command

    @Serializable
    @SerialName("grant")
    data class Grant(@SerialName("req_id") val requestId: String, val minutes: Int) : Command

    @Serializable
    @SerialName("deny")
    data class Deny(@SerialName("req_id") val requestId: String) : Command

    /**
     * Rules are opaque here on purpose: the engine owns their shape, and the transport
     * should not have to be changed every time a rule type is added. A [rev] that is not
     * higher than the current one is ignored by the receiver, so a duplicated message
     * cannot roll the rules back.
     */
    @Serializable
    @SerialName("set_rules")
    data class SetRules(val rev: Int, val rules: JsonObject) : Command

    @Serializable
    @SerialName("stop_app")
    data class StopApp(val pkg: String) : Command

    @Serializable
    @SerialName("ping")
    data object Ping : Command
}
