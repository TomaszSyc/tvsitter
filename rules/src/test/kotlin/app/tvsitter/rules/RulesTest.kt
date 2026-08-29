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
import org.junit.jupiter.api.Assertions.assertFalse
import org.junit.jupiter.api.Assertions.assertNull
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test
import java.time.DayOfWeek
import java.time.LocalTime

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

    @Test
    fun `merging one app's budget keeps the others`() {
        // The case the deep merge exists for. A control that sets one package must not be able
        // to wipe the rest, and Home Assistant cannot read the current map first: the rules
        // live on the television.
        val merged = Rules.merge(
            json("""{"app_limits_s": {"com.netflix.ninja": 1800, "com.google.android.youtube.tv": 600}}"""),
            json("""{"app_limits_s": {"com.netflix.ninja": 3600}}"""),
        )

        assertEquals(
            json("""{"app_limits_s": {"com.google.android.youtube.tv": 600, "com.netflix.ninja": 3600}}"""),
            merged,
        )
    }

    @Test
    fun `a nested null removes one app's budget and leaves the others`() {
        val merged = Rules.merge(
            json("""{"app_limits_s": {"com.netflix.ninja": 1800, "com.google.android.youtube.tv": 600}}"""),
            json("""{"app_limits_s": {"com.netflix.ninja": null}}"""),
        )

        assertEquals(json("""{"app_limits_s": {"com.google.android.youtube.tv": 600}}"""), merged)
    }

    @Test
    fun `a null on the object clears all of them at once`() {
        val merged = Rules.merge(
            json("""{"app_limits_s": {"com.netflix.ninja": 1800}, "daily_limit_s": 3600}"""),
            json("""{"app_limits_s": null}"""),
        )

        assertEquals(json("""{"daily_limit_s": 3600}"""), merged)
    }

    @Test
    fun `emptying an object leaves the object, not a removal`() {
        // Nothing reads the two differently. Dropping the container would mean removing the last
        // app's budget also removed the thing that holds them, which is a rule needing an excuse.
        val merged = Rules.merge(
            json("""{"app_limits_s": {"com.netflix.ninja": 1800}}"""),
            json("""{"app_limits_s": {"com.netflix.ninja": null}}"""),
        )

        assertEquals(json("""{"app_limits_s": {}}"""), merged)
    }

    @Test
    fun `a list replaces whole rather than merging`() {
        // A window has no key identity to merge on, and half a schedule is worse than the one
        // that was already there.
        val merged = Rules.merge(
            json("""{"windows": [{"id": "school"}, {"id": "weekend"}]}"""),
            json("""{"windows": [{"id": "holidays"}]}"""),
        )

        assertEquals(json("""{"windows": [{"id": "holidays"}]}"""), merged)
    }

    @Test
    fun `an object arriving where a number was is taken as it comes`() {
        // Not a merge: there is nothing to merge with. A rule that changed shape between
        // versions replaces, rather than leaving something half of each.
        val merged = Rules.merge(
            json("""{"days": 3600}"""),
            json("""{"days": {"sat": 7200}}"""),
        )

        assertEquals(json("""{"days": {"sat": 7200}}"""), merged)
    }

    @Test
    fun `nesting deeper than the rules go replaces rather than recursing`() {
        // The rules are two levels deep. The bound is here because this walks a payload from
        // the network, and the service that enforces the limit must not be killable by one.
        val merged = Rules.merge(
            json("""{"a": {"b": {"c": {"d": {"keep": 1}}}}}"""),
            json("""{"a": {"b": {"c": {"d": {"add": 2}}}}}"""),
        )

        assertEquals(json("""{"a": {"b": {"c": {"d": {"add": 2}}}}}"""), merged)
    }

    @Test
    fun `a day's own limit wins over the plain daily one`() {
        val rules = Rules.fromJson(json("""{"daily_limit_s": 3600, "days": {"sat": 7200}}"""))

        assertEquals(7200, rules.limitFor(DayOfWeek.SATURDAY))
        assertEquals(3600, rules.limitFor(DayOfWeek.MONDAY))
    }

    @Test
    fun `a day set to zero is no viewing, not no limit`() {
        // The distinction the daily limit has always made, one level down.
        val rules = Rules.fromJson(json("""{"daily_limit_s": 3600, "days": {"wed": 0}}"""))

        assertEquals(0, rules.limitFor(DayOfWeek.WEDNESDAY))
    }

    @Test
    fun `a day override without a daily limit leaves the other days unlimited`() {
        val rules = Rules.fromJson(json("""{"days": {"sat": 7200}}"""))

        assertEquals(7200, rules.limitFor(DayOfWeek.SATURDAY))
        assertNull(rules.limitFor(DayOfWeek.MONDAY))
    }

    @Test
    fun `an app limit of zero is a blocked app, not an app without one`() {
        val rules = Rules.fromJson(
            json("""{"app_limits_s": {"com.twitch.android.app": 0, "com.netflix.ninja": 1800}}"""),
        )

        assertEquals(0, rules.appLimitSeconds["com.twitch.android.app"])
        assertEquals(1800, rules.appLimitSeconds["com.netflix.ninja"])
        assertNull(rules.appLimitSeconds["com.google.android.youtube.tv"])
    }

    @Test
    fun `warnings are five minutes until somebody says otherwise`() {
        // An absent key is "the ordinary amount", because a parent who has never touched this
        // should still get a warning. Zero is what says none, and it needs to stay free to.
        assertEquals(listOf(300L), Rules.fromJson(json("{}")).warnBeforeSeconds)
    }

    @Test
    fun `an empty list is no warnings, and so is a zero`() {
        assertEquals(emptyList<Long>(), Rules.fromJson(json("""{"warn_before_s": []}""")).warnBeforeSeconds)
        assertEquals(emptyList<Long>(), Rules.fromJson(json("""{"warn_before_s": [0]}""")).warnBeforeSeconds)
        assertEquals(emptyList<Long>(), Rules.fromJson(json("""{"warn_before_s": 0}""")).warnBeforeSeconds)
    }

    @Test
    fun `warnings come back farthest first however they were written`() {
        // The order the television will use them in, decided here rather than at every reading.
        val rules = Rules.fromJson(json("""{"warn_before_s": [300, 900, 300]}"""))

        assertEquals(listOf(900L, 300L), rules.warnBeforeSeconds)
    }

    @Test
    fun `one number is accepted where a list belongs`() {
        // What anyone types first, and refusing it would enforce a shape rather than a rule.
        assertEquals(listOf(600L), Rules.fromJson(json("""{"warn_before_s": 600}""")).warnBeforeSeconds)
    }

    @Test
    fun `a rule that cannot be read is named rather than dropped in silence`() {
        // This degrades towards *less* enforcement — a dropped window widens the evening — so
        // nothing may go missing without something to log.
        val reading = Rules.read(
            json("""{"daily_limit_s": "an hour", "days": {"funday": 60}, "windows": [{"from": "16:00"}]}"""),
        )

        assertNull(reading.rules.dailyLimitSeconds)
        assertEquals(listOf("daily_limit_s", "days.funday", "windows[0]"), reading.ignored)
    }

    @Test
    fun `rules that read cleanly report nothing to log`() {
        val reading = Rules.read(json("""{"daily_limit_s": 3600, "days": {"sat": 7200}}"""))

        assertEquals(emptyList<String>(), reading.ignored)
    }

    @Test
    fun `one unreadable window does not take the readable ones with it`() {
        val reading = Rules.read(
            json(
                """{"windows": [{"id": "school", "from": "16:00", "to": "19:30"}, {"id": "broken"}]}""",
            ),
        )

        assertEquals(1, reading.rules.windows.size)
        assertEquals("school", reading.rules.windows.first().id)
        assertEquals(listOf("windows[1]"), reading.ignored)
    }

    @Test
    fun `everything survives the round trip it will make over MQTT`() {
        val rules = Rules(
            dailyLimitSeconds = 3600,
            dayLimitSeconds = mapOf(DayOfWeek.SATURDAY to 7200),
            windows = listOf(Window("school", LocalTime.of(16, 0), LocalTime.of(19, 30), setOf(DayOfWeek.MONDAY))),
            appLimitSeconds = mapOf("com.netflix.ninja" to 1800),
            warnBeforeSeconds = listOf(900, 300),
        )

        assertEquals(rules, Rules.fromJson(rules.toJson()))
    }

    @Test
    fun `rules nobody has touched encode to nothing at all`() {
        // Including the warning default: writing it out would turn "the ordinary amount" into a
        // setting, and then changing the default later would not reach anybody.
        assertTrue(Rules.NONE.toJson().isEmpty(), Rules.NONE.toJson().toString())
    }

    @Test
    fun `blocking settings is a switch, not a number of minutes`() {
        // Twenty minutes of Settings a day is not a thing anybody means.
        val rules = Rules.fromJson(json("""{"block_settings": true}"""))

        assertTrue(rules.settingsBlocked)
    }

    @Test
    fun `settings are reachable unless somebody said otherwise`() {
        assertFalse(Rules.fromJson(json("{}")).settingsBlocked)
        assertFalse(Rules.fromJson(json("""{"block_settings": false}""")).settingsBlocked)
        assertFalse(Rules.fromJson(json("""{"block_settings": null}""")).settingsBlocked)
    }

    @Test
    fun `an unreadable flag leaves the door open rather than shut`() {
        // The direction matters. A rule nobody can parse must not keep a parent out of their
        // own Settings — that is the failure that gets this uninstalled rather than debugged.
        val reading = Rules.read(json("""{"block_settings": "yes please"}"""))

        assertFalse(reading.rules.settingsBlocked)
        assertTrue(reading.ignored.contains("block_settings"))
    }

    @Test
    fun `the switch survives the round trip it will make over MQTT`() {
        val blocked = Rules(settingsBlocked = true)

        assertEquals(blocked, Rules.fromJson(blocked.toJson()))
    }
}
