/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.rules

import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.add
import kotlinx.serialization.json.booleanOrNull
import kotlinx.serialization.json.buildJsonArray
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.longOrNull
import kotlinx.serialization.json.put
import java.time.DayOfWeek

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
data class Rules(
    val dailyLimitSeconds: Long? = null,
    /** Days that do not take [dailyLimitSeconds]. A day that is absent here takes it. */
    val dayLimitSeconds: Map<DayOfWeek, Long> = emptyMap(),
    /** Empty means the hours are not restricted. See [Window] and D27. */
    val windows: List<Window> = emptyList(),
    /** Per package. Zero is a blocked app, which is why it is not the same as being absent. */
    val appLimitSeconds: Map<String, Long> = emptyMap(),
    /**
     * How long before the end to say so, farthest first. Empty means say nothing.
     *
     * A list rather than a number because two warnings — a quarter of an hour, then five
     * minutes — is a thing people want, and it is awkward to retrofit onto a single control
     * somebody already has on a dashboard (#39).
     */
    val warnBeforeSeconds: List<Long> = DEFAULT_WARNINGS,
    /**
     * Whether the Settings app is kept out of reach, lock or no lock.
     *
     * A switch rather than a budget, because "twenty minutes of Settings a day" is not a thing
     * anybody means. It is the one app whose reach decides whether any of the others can be
     * enforced at all: force-stop, "draw on top" and the date all live behind it (D30).
     */
    val settingsBlocked: Boolean = false,
) {

    /** The limit in force on [day], which is the day's own or the plain daily one. */
    fun limitFor(day: DayOfWeek): Long? = dayLimitSeconds[day] ?: dailyLimitSeconds

    fun toJson(): JsonObject = buildJsonObject {
        dailyLimitSeconds?.let { put(KEY_DAILY_LIMIT, it) }
        if (dayLimitSeconds.isNotEmpty()) {
            put(KEY_DAYS, buildJsonObject { dayLimitSeconds.forEach { (day, s) -> put(nameOf(day), s) } })
        }
        if (windows.isNotEmpty()) put(KEY_WINDOWS, buildJsonArray { windows.forEach { add(it.toJson()) } })
        if (appLimitSeconds.isNotEmpty()) {
            put(KEY_APP_LIMITS, buildJsonObject { appLimitSeconds.forEach { (app, s) -> put(app, s) } })
        }
        // Only when it is not the default, so that rules nobody has touched encode to nothing
        // at all. An absent key means "warn the ordinary amount", not "do not warn".
        if (warnBeforeSeconds != DEFAULT_WARNINGS) {
            put(KEY_WARN_BEFORE, buildJsonArray { warnBeforeSeconds.forEach { add(it) } })
        }
        if (settingsBlocked) put(KEY_BLOCK_SETTINGS, true)
    }

    companion object {
        const val KEY_DAILY_LIMIT: String = "daily_limit_s"
        const val KEY_DAYS: String = "days"
        const val KEY_WINDOWS: String = "windows"
        const val KEY_APP_LIMITS: String = "app_limits_s"
        const val KEY_WARN_BEFORE: String = "warn_before_s"
        const val KEY_BLOCK_SETTINGS: String = "block_settings"

        /**
         * Five minutes, as it has been since M2.
         *
         * The default belongs to an absent key rather than to a zero: somebody who has never
         * touched this should still get a warning, and zero has to be free to mean "none" (#39).
         */
        val DEFAULT_WARNINGS: List<Long> = listOf(300)

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
         * Reads rules from a `set_rules` payload, along with what it could not read.
         *
         * An absent key means the rule is not in force. A key present but unreadable means the
         * same and is worth a caller's warning: guessing a number here would invent a limit
         * nobody set, and inventing a limit is worse than enforcing none.
         *
         * Which is also why nothing is dropped quietly. Every unreadable rule is named in
         * [RulesReading.ignored] for the caller to log, because the direction this degrades in
         * is *less* enforcement — a dropped window widens the evening — and a change in what a
         * television enforces cannot be something nobody could have noticed.
         */
        fun read(json: JsonObject): RulesReading {
            val ignored = mutableListOf<String>()
            return RulesReading(
                Rules(
                    dailyLimitSeconds = secondsIn(json[KEY_DAILY_LIMIT], KEY_DAILY_LIMIT, ignored),
                    dayLimitSeconds = readDayLimits(json[KEY_DAYS], ignored),
                    windows = readWindows(json[KEY_WINDOWS], ignored),
                    appLimitSeconds = readAppLimits(json[KEY_APP_LIMITS], ignored),
                    warnBeforeSeconds = readWarnings(json[KEY_WARN_BEFORE], ignored),
                    settingsBlocked = readFlag(json[KEY_BLOCK_SETTINGS], KEY_BLOCK_SETTINGS, ignored),
                ),
                ignored,
            )
        }

        fun fromJson(json: JsonObject): Rules = read(json).rules
    }
}

/** Rules as they were read, and every rule that could not be. */
data class RulesReading(val rules: Rules, val ignored: List<String>)

/**
 * A count of seconds, floored at zero, or null when there is nothing readable there.
 *
 * A negative limit is floored rather than refused: whoever sent it meant "none of that", which
 * zero says exactly. Text where a number belongs is a different thing and is reported.
 */
private fun secondsIn(element: JsonElement?, name: String, ignored: MutableList<String>): Long? {
    if (element == null || element is JsonNull) return null
    val seconds = (element as? JsonPrimitive)?.longOrNull
    if (seconds == null) {
        ignored += name
        return null
    }
    return seconds.coerceAtLeast(0)
}

private fun readDayLimits(element: JsonElement?, ignored: MutableList<String>): Map<DayOfWeek, Long> {
    val json = element as? JsonObject ?: return emptyMap<DayOfWeek, Long>().also {
        if (element != null && element !is JsonNull) ignored += Rules.KEY_DAYS
    }
    val limits = mutableMapOf<DayOfWeek, Long>()
    for ((name, value) in json) {
        val day = dayOf(name)
        if (day == null) {
            ignored += "${Rules.KEY_DAYS}.$name"
            continue
        }
        secondsIn(value, "${Rules.KEY_DAYS}.$name", ignored)?.let { limits[day] = it }
    }
    return limits
}

private fun readAppLimits(element: JsonElement?, ignored: MutableList<String>): Map<String, Long> {
    val json = element as? JsonObject ?: return emptyMap<String, Long>().also {
        if (element != null && element !is JsonNull) ignored += Rules.KEY_APP_LIMITS
    }
    val limits = mutableMapOf<String, Long>()
    for ((app, value) in json) {
        if (app.isBlank()) {
            ignored += Rules.KEY_APP_LIMITS
            continue
        }
        secondsIn(value, "${Rules.KEY_APP_LIMITS}.$app", ignored)?.let { limits[app] = it }
    }
    return limits
}

private fun readWindows(element: JsonElement?, ignored: MutableList<String>): List<Window> {
    val array = element as? JsonArray ?: return emptyList<Window>().also {
        if (element != null && element !is JsonNull) ignored += Rules.KEY_WINDOWS
    }
    val windows = mutableListOf<Window>()
    array.forEachIndexed { index, entry ->
        val window = (entry as? JsonObject)?.let { Window.read(it) }
        if (window == null) {
            ignored += "${Rules.KEY_WINDOWS}[$index]"
        } else {
            windows += window
        }
    }
    return windows
}

/**
 * The warning thresholds, farthest first.
 *
 * Zeros are dropped rather than kept: nothing is ever "zero seconds from the end" without being
 * past it, so a zero in the list is how somebody spells "no warning" — and an empty list is what
 * that means here. Duplicates are dropped because the same warning twice is one warning.
 */
private fun readWarnings(element: JsonElement?, ignored: MutableList<String>): List<Long> {
    if (element == null || element is JsonNull) return Rules.DEFAULT_WARNINGS
    val array = element as? JsonArray
    if (array == null) {
        // A single number, which is what anyone would try first, and it costs nothing to accept.
        val one = (element as? JsonPrimitive)?.longOrNull
        if (one == null) {
            ignored += Rules.KEY_WARN_BEFORE
            return Rules.DEFAULT_WARNINGS
        }
        return listOf(one).filter { it > 0 }
    }
    val thresholds = mutableListOf<Long>()
    array.forEachIndexed { index, entry ->
        val seconds = (entry as? JsonPrimitive)?.longOrNull
        if (seconds == null) ignored += "${Rules.KEY_WARN_BEFORE}[$index]" else thresholds += seconds
    }
    return thresholds.filter { it > 0 }.distinct().sortedDescending()
}

/**
 * A yes or a no, and nothing else.
 *
 * Anything unreadable is a no, and says so. The direction matters: a rule nobody can parse must
 * not silently keep a parent out of their own Settings, which is the failure that would have
 * them uninstall this rather than debug it.
 */
private fun readFlag(element: JsonElement?, name: String, ignored: MutableList<String>): Boolean {
    if (element == null || element is JsonNull) return false
    val flag = (element as? JsonPrimitive)?.booleanOrNull
    if (flag == null) {
        ignored += name
        return false
    }
    return flag
}
