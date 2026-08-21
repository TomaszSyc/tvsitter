/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.rules.pairing

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json

/**
 * The pairing protocol: one POST, once, and then the endpoint is gone.
 *
 * Kept beside the MQTT contract and shared the same way, because it is the other interface
 * between the two halves. Everything the running system needs travels over MQTT; this
 * exists only to tell a TV which broker to talk to, so it stays deliberately small.
 */
object PairingProtocol {
    const val SERVICE_TYPE: String = "_tvsitter._tcp"
    const val PATH: String = "/pair"

    /** mDNS TXT keys, so the integration can identify a TV before talking to it. */
    const val TXT_DEVICE_ID: String = "id"
    const val TXT_NAME: String = "name"
    const val TXT_VERSION: String = "version"
    const val TXT_PAIRED: String = "paired"

    /** Caps for the hand-rolled server. Small on purpose; the payload is tiny. */
    const val MAX_REQUEST_BYTES: Int = 4096
    const val SOCKET_TIMEOUT_MS: Int = 5000

    val json: Json = Json {
        ignoreUnknownKeys = true
        encodeDefaults = true
    }
}

/** What Home Assistant posts to `/pair`. */
@Serializable
data class PairRequest(
    val pin: String,
    val host: String,
    val port: Int = 1883,
    val username: String = "",
    val password: String = "",
    @SerialName("topic_prefix") val topicPrefix: String,
    @SerialName("use_tls") val useTls: Boolean = false,
)

/**
 * What the TV answers.
 *
 * [attemptsRemaining] is returned on a wrong PIN so the integration can say how many tries
 * are left rather than leaving somebody guessing blind — the code is on the screen in front
 * of them, so this leaks nothing an honest user does not already have.
 */
@Serializable
data class PairResponse(
    val ok: Boolean,
    val error: String? = null,
    @SerialName("attempts_remaining") val attemptsRemaining: Int? = null,
    @SerialName("device_id") val deviceId: String? = null,
    val name: String? = null,
) {
    companion object {
        const val ERROR_WRONG_PIN: String = "wrong_pin"
        const val ERROR_EXPIRED: String = "expired"
        const val ERROR_NO_ATTEMPTS: String = "no_attempts_left"
        const val ERROR_ALREADY_USED: String = "already_used"
        const val ERROR_NOT_PAIRING: String = "pairing_not_active"
        const val ERROR_BAD_REQUEST: String = "bad_request"

        fun accepted(deviceId: String, name: String): PairResponse =
            PairResponse(ok = true, deviceId = deviceId, name = name)

        fun rejected(error: String, attemptsRemaining: Int? = null): PairResponse =
            PairResponse(ok = false, error = error, attemptsRemaining = attemptsRemaining)
    }
}
