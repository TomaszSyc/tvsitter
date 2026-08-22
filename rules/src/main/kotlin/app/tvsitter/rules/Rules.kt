/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.rules

import kotlinx.serialization.json.JsonNull
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

        /**
         * Folds an incoming `set_rules` object into the stored one.
         *
         * `set_rules` merges rather than replaces, and a key carrying `null` removes it. The
         * alternative is a full replacement, which forces whoever is editing to know every
         * rule in force — and since the TV keeps the rules (D3), that means publishing all of
         * them and hoping the two copies agree. It also means two controls on a dashboard can
         * clobber each other's unrelated rules, which is a bug nobody would suspect.
         *
         * An empty object therefore changes nothing, which is worth saying out loud because
         * the obvious reading is the opposite.
         */
        fun merge(current: JsonObject, incoming: JsonObject): JsonObject = buildJsonObject {
            val removed = incoming.filterValues { it is JsonNull }.keys
            for ((key, value) in current) {
                if (key !in removed && key !in incoming) put(key, value)
            }
            for ((key, value) in incoming) {
                if (value !is JsonNull) put(key, value)
            }
        }

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
