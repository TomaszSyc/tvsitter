/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.rules

import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.add
import kotlinx.serialization.json.buildJsonArray
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.put
import java.time.DayOfWeek
import java.time.LocalTime

/**
 * A stretch of the day when watching is allowed.
 *
 * Wall-clock times, deliberately: converting them into the budget day's frame needs the day
 * start, which belongs to [BudgetClock] and not to a rule somebody typed. The engine does that
 * conversion when it evaluates; a window on its own is just "from this time to that one".
 *
 * [days] empty means every day. That is not the same as a window nobody can reach — an absent
 * `days` key is the ordinary case for a house with one rule for the whole week.
 */
data class Window(val id: String, val from: LocalTime, val to: LocalTime, val days: Set<DayOfWeek> = emptySet()) {
    fun appliesOn(day: DayOfWeek): Boolean = days.isEmpty() || day in days

    fun toJson(): JsonObject = buildJsonObject {
        put(KEY_ID, id)
        // `16:00`, because LocalTime leaves the seconds off when there are none — the same
        // shape that went in, which is what makes a published rules object readable.
        put(KEY_FROM, from.toString())
        put(KEY_TO, to.toString())
        if (days.isNotEmpty()) {
            put(KEY_DAYS, buildJsonArray { days.sorted().forEach { add(nameOf(it)) } })
        }
    }

    companion object {
        const val KEY_ID: String = "id"
        const val KEY_FROM: String = "from"
        const val KEY_TO: String = "to"
        const val KEY_DAYS: String = "days"

        /**
         * Reads one window, or null when it is not usable.
         *
         * Null rather than a default, and never a guess: a window is a permission, so inventing
         * one would hand over an evening nobody granted, and inventing its hours would take one
         * away. The caller drops it and says so — [Rules.read] collects the reasons so that a
         * dropped window cannot be a silent change of what is enforced.
         */
        fun read(json: JsonObject): Window? {
            val id = (json[KEY_ID] as? JsonPrimitive)?.contentOrNull?.takeIf { it.isNotBlank() }
            val from = timeOf(json[KEY_FROM])
            val to = timeOf(json[KEY_TO])
            if (id == null || from == null || to == null) return null

            // A window that starts when it ends is not a short window, it is a mistake. Read as
            // "all day" it would hand over the day; read as "no time" it would take one away.
            if (from == to) return null

            return Window(id, from, to, daysOf(json[KEY_DAYS]))
        }

        private fun daysOf(element: JsonElement?): Set<DayOfWeek> {
            val array = runCatching { element?.jsonArray }.getOrNull() ?: return emptySet()
            return array.mapNotNull { dayOf((it as? JsonPrimitive)?.contentOrNull) }.toSet()
        }
    }
}

/** `mon` through `sun`, which is what the rules use and what a person can read in a payload. */
private val DAY_NAMES: Map<String, DayOfWeek> = mapOf(
    "mon" to DayOfWeek.MONDAY,
    "tue" to DayOfWeek.TUESDAY,
    "wed" to DayOfWeek.WEDNESDAY,
    "thu" to DayOfWeek.THURSDAY,
    "fri" to DayOfWeek.FRIDAY,
    "sat" to DayOfWeek.SATURDAY,
    "sun" to DayOfWeek.SUNDAY,
)

/**
 * A day name, three letters or written out.
 *
 * `mon` is the shape the rules use and the shape they are published in. `monday` is what a
 * person types by hand the first time, and refusing it would cost somebody an evening working
 * out why their Monday rule did nothing.
 */
fun dayOf(name: String?): DayOfWeek? {
    val text = name?.trim()?.lowercase() ?: return null
    return DAY_NAMES[text] ?: runCatching { DayOfWeek.valueOf(text.uppercase()) }.getOrNull()
}

fun nameOf(day: DayOfWeek): String = DAY_NAMES.entries.first { it.value == day }.key

/**
 * `HH:MM`, and nothing else.
 *
 * Strict on purpose. `LocalTime.parse` would accept `16:00:30.5`, and a rule with seconds in it
 * is a rule somebody will later swear they did not write.
 */
fun timeOf(element: JsonElement?): LocalTime? {
    val text = (element as? JsonPrimitive)?.contentOrNull ?: return null
    if (!TIME_FORMAT.matches(text)) return null
    return runCatching { LocalTime.parse(text) }.getOrNull()
}

private val TIME_FORMAT = Regex("""^([01]\d|2[0-3]):[0-5]\d$""")
