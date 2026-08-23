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
         * How deep a merge goes before it starts replacing instead.
         *
         * The rules are two levels deep — an object of rules, some of which are objects keyed by
         * day or by package — so four is slack rather than a limit anyone will meet. It is here
         * because this recurses over a payload that arrives from the network, and a service that
         * enforces a limit must not be killable by a deeply nested object.
         */
        private const val MAX_DEPTH = 4

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
         *
         * The merge reaches **inside** objects, and that is the whole point of it now that a
         * rule's value can be an object: a per-app budget names one package, and a shallow
         * merge would replace the map and drop every other app's budget silently. Home
         * Assistant cannot avoid that by reading the current map first, because the rules live
         * on the television. So an object merges key by key, a `null` removes at any depth, and
         * arrays and scalars replace whole — a list has no key identity to merge on, and half a
         * schedule is worse than the one that was there.
         *
         * Emptying a nested object leaves the empty object behind rather than removing it.
         * Nothing reads the two differently, and dropping the container would mean removing the
         * last app's budget also removed the thing that holds them, which is a rule that would
         * need explaining. Clearing all of them at once is what a `null` on the container is for.
         */
        fun merge(current: JsonObject, incoming: JsonObject): JsonObject = merge(current, incoming, depth = 1)

        private fun merge(current: JsonObject, incoming: JsonObject, depth: Int): JsonObject = buildJsonObject {
            for ((key, value) in current) {
                if (key !in incoming) put(key, value)
            }
            for ((key, value) in incoming) {
                val existing = current[key]
                when {
                    value is JsonNull -> Unit
                    value is JsonObject && existing is JsonObject && depth < MAX_DEPTH ->
                        put(key, merge(existing, value, depth + 1))

                    else -> put(key, value)
                }
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
