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

class WindowTest {

    private fun json(text: String): JsonObject = Json.parseToJsonElement(text).jsonObject

    private val afternoon = json(
        """{"id": "school", "from": "16:00", "to": "19:30", "days": ["mon", "tue"]}""",
    )

    @Test
    fun `a window reads the shape a person would type`() {
        val window = Window.read(afternoon)

        assertEquals(
            Window("school", LocalTime.of(16, 0), LocalTime.of(19, 30), setOf(DayOfWeek.MONDAY, DayOfWeek.TUESDAY)),
            window,
        )
    }

    @Test
    fun `no days means every day, not no days`() {
        val window = Window.read(json("""{"id": "always", "from": "09:00", "to": "21:00"}"""))!!

        assertTrue(window.appliesOn(DayOfWeek.WEDNESDAY), "a window nobody dated applies every day")
        assertTrue(window.appliesOn(DayOfWeek.SUNDAY))
    }

    @Test
    fun `a window with days applies only on those days`() {
        val window = Window.read(afternoon)!!

        assertTrue(window.appliesOn(DayOfWeek.MONDAY))
        assertFalse(window.appliesOn(DayOfWeek.SATURDAY))
    }

    @Test
    fun `a window with no id is dropped, because nothing could name it afterwards`() {
        // The id is what `active_window` publishes, and answering "why did it block me" is the
        // reason that field exists.
        assertNull(Window.read(json("""{"from": "16:00", "to": "19:30"}""")))
        assertNull(Window.read(json("""{"id": "  ", "from": "16:00", "to": "19:30"}""")))
    }

    @Test
    fun `a window that starts when it ends is a mistake, not a short window`() {
        // Read as all day it hands over the day; read as no time it takes one away. Neither is
        // a guess worth making.
        assertNull(Window.read(json("""{"id": "noon", "from": "12:00", "to": "12:00"}""")))
    }

    @Test
    fun `a time is HH colon MM and nothing else`() {
        // LocalTime.parse would take the first two of these, and a rule with seconds in it is a
        // rule somebody will later swear they did not write.
        assertNull(timeOf(Json.parseToJsonElement(""""16:00:30"""")))
        assertNull(timeOf(Json.parseToJsonElement(""""16:00:30.5"""")))
        assertNull(timeOf(Json.parseToJsonElement(""""4pm"""")))
        assertNull(timeOf(Json.parseToJsonElement(""""24:00"""")))
        assertNull(timeOf(Json.parseToJsonElement("1600")))
        assertEquals(LocalTime.of(23, 59), timeOf(Json.parseToJsonElement(""""23:59"""")))
        assertEquals(LocalTime.MIDNIGHT, timeOf(Json.parseToJsonElement(""""00:00"""")))
    }

    @Test
    fun `day names are read three letters or written out, in any case`() {
        assertEquals(DayOfWeek.MONDAY, dayOf("mon"))
        assertEquals(DayOfWeek.MONDAY, dayOf("Monday"))
        assertEquals(DayOfWeek.SUNDAY, dayOf(" SUN "))
        assertNull(dayOf("caturday"))
        assertNull(dayOf(null))
    }

    @Test
    fun `an unknown day is dropped and the rest of the window stands`() {
        val window = Window.read(
            json("""{"id": "weekend", "from": "09:00", "to": "21:00", "days": ["sat", "caturday"]}"""),
        )!!

        assertEquals(setOf(DayOfWeek.SATURDAY), window.days)
    }

    @Test
    fun `a window survives the round trip it will make over MQTT`() {
        val window = Window.read(afternoon)!!

        assertEquals(window, Window.read(window.toJson()))
        assertEquals(afternoon, window.toJson())
    }

    @Test
    fun `a window that applies every day encodes without a day list`() {
        val window = Window("always", LocalTime.of(9, 0), LocalTime.of(21, 0))

        assertEquals(json("""{"id": "always", "from": "09:00", "to": "21:00"}"""), window.toJson())
    }
}
