/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.rules

import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.longOrNull

/**
 * What the TV is enforcing.
 *
 * Deliberately small. `set_rules` carries an opaque object in the contract so that the engine
 * owns the shape and the transport does not have to be revised every time a rule is added;
 * this is that shape, at the point where it holds one rule.
 *
 * [dailyLimitSeconds] is null for "no limit", which is not zero. Zero is a real setting — no
 * viewing today — and conflating the two would either lock a TV nobody meant to lock or fail
 * to lock one somebody did.
 */
data class Rules(val dailyLimitSeconds: Long? = null) {

    fun toJson(): JsonObject = buildJsonObject {
        dailyLimitSeconds?.let { put(KEY_DAILY_LIMIT, JsonPrimitive(it)) }
    }

    companion object {
        const val KEY_DAILY_LIMIT: String = "daily_limit_s"

        val NONE: Rules = Rules()

        /**
         * Reads rules from a `set_rules` payload.
         *
         * An absent key means no limit. A key present but unreadable is treated the same way
         * and is worth a caller's warning: guessing a number here would invent a limit
         * nobody set, and inventing a limit is worse than enforcing none.
         */
        fun fromJson(json: JsonObject): Rules {
            val raw = json[KEY_DAILY_LIMIT] ?: return NONE
            val seconds = (raw as? JsonPrimitive)?.longOrNull ?: return NONE
            return Rules(dailyLimitSeconds = seconds.coerceAtLeast(0))
        }
    }
}
