/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.rules

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonObject
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertNull
import org.junit.jupiter.api.Test

class RulesTest {

    private fun json(text: String): JsonObject = Json.parseToJsonElement(text).jsonObject

    @Test
    fun `a limit survives the round trip it will make over MQTT`() {
        val rules = Rules(dailyLimitSeconds = 5_400)

        assertEquals(rules, Rules.fromJson(rules.toJson()))
    }

    @Test
    fun `no limit is the absence of the key, not a zero`() {
        assertEquals(JsonObject(emptyMap()), Rules.NONE.toJson())
        assertNull(Rules.fromJson(json("{}")).dailyLimitSeconds)
    }

    @Test
    fun `zero is a real setting and is kept`() {
        // Nothing at all today is a thing a parent may mean, and it is not the same as
        // lifting the limit.
        assertEquals(0, Rules.fromJson(json("""{"daily_limit_s": 0}""")).dailyLimitSeconds)
    }

    @Test
    fun `a negative limit is floored rather than trusted`() {
        assertEquals(0, Rules.fromJson(json("""{"daily_limit_s": -600}""")).dailyLimitSeconds)
    }

    @Test
    fun `an unreadable limit enforces none rather than a guess`() {
        // Inventing a number here would impose a limit nobody set, which is worse than
        // enforcing none and saying so.
        assertNull(Rules.fromJson(json("""{"daily_limit_s": "an hour"}""")).dailyLimitSeconds)
        assertNull(Rules.fromJson(json("""{"daily_limit_s": null}""")).dailyLimitSeconds)
    }

    @Test
    fun `rules it does not understand are ignored rather than refused`() {
        // The contract keeps `rules` opaque so a newer Home Assistant can send more than this
        // build knows about. Refusing the whole object would drop the limit as well.
        val rules = Rules.fromJson(json("""{"daily_limit_s": 60, "weekday_window": "16-19"}"""))

        assertEquals(60, rules.dailyLimitSeconds)
    }

    @Test
    fun `merging keeps rules the sender said nothing about`() {
        // The case this exists for: a control that only knows about the limit must not wipe a
        // schedule it has never heard of.
        val merged = Rules.merge(
            json("""{"daily_limit_s": 3600, "weekday_window": "16-19"}"""),
            json("""{"daily_limit_s": 1800}"""),
        )

        assertEquals(json("""{"weekday_window": "16-19", "daily_limit_s": 1800}"""), merged)
    }

    @Test
    fun `a null removes just that rule`() {
        val merged = Rules.merge(
            json("""{"daily_limit_s": 3600, "weekday_window": "16-19"}"""),
            json("""{"daily_limit_s": null}"""),
        )

        assertEquals(json("""{"weekday_window": "16-19"}"""), merged)
        assertNull(Rules.fromJson(merged).dailyLimitSeconds)
    }

    @Test
    fun `an empty object changes nothing, which is the opposite of the obvious reading`() {
        val current = json("""{"daily_limit_s": 3600}""")

        assertEquals(current, Rules.merge(current, json("{}")))
    }

    @Test
    fun `merging into nothing is just the incoming rules`() {
        assertEquals(
            json("""{"daily_limit_s": 600}"""),
            Rules.merge(json("{}"), json("""{"daily_limit_s": 600}""")),
        )
    }
}
