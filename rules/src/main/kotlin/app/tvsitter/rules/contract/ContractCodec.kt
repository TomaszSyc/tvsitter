/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.rules.contract

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonPrimitive

/** Raised when a payload declares a schema this build does not understand. */
class UnsupportedSchemaException(val found: Int, val supported: Int) :
    IllegalArgumentException("payload schema $found is newer than supported schema $supported")

/**
 * Encodes and decodes the MQTT payloads.
 *
 * Unknown keys are ignored so that adding a field does not break older readers, while a
 * higher `schema` is refused outright — at that point the meaning of existing fields can no
 * longer be assumed, and guessing is worse than failing loudly.
 */
object ContractCodec {

    private val json = Json {
        ignoreUnknownKeys = true
        encodeDefaults = true
        explicitNulls = true
    }

    fun encode(snapshot: StateSnapshot): String = json.encodeToString(snapshot)

    fun encode(request: TimeRequest): String = json.encodeToString(request)

    fun encode(command: Command): String = json.encodeToString(command)

    fun decodeState(payload: String): StateSnapshot {
        requireSupportedSchema(payload)
        return json.decodeFromString(payload)
    }

    fun decodeRequest(payload: String): TimeRequest {
        requireSupportedSchema(payload)
        return json.decodeFromString(payload)
    }

    fun encode(day: DaySummary): String = json.encodeToString(day)

    fun decodeDay(payload: String): DaySummary {
        requireSupportedSchema(payload)
        return json.decodeFromString(payload)
    }

    fun encode(alert: Alert): String = json.encodeToString(alert)

    fun decodeAlert(payload: String): Alert {
        requireSupportedSchema(payload)
        return json.decodeFromString(payload)
    }

    fun decodeCommand(payload: String): Command = json.decodeFromString(payload)

    /**
     * Reads `schema` before deserialising properly. A payload without the field is treated
     * as the current schema: it is either an old sender or a hand-written test message, and
     * in both cases the fields present mean what they mean today.
     */
    private fun requireSupportedSchema(payload: String) {
        val found = runCatching {
            json.parseToJsonElement(payload)
                .let { it as? JsonObject }
                ?.get("schema")
                ?.jsonPrimitive
                ?.content
                ?.toIntOrNull()
        }.getOrNull() ?: return

        if (found > Contract.SCHEMA_VERSION) {
            throw UnsupportedSchemaException(found, Contract.SCHEMA_VERSION)
        }
    }
}
