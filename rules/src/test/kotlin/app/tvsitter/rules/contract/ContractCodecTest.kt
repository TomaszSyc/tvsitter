/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.rules.contract

import app.tvsitter.rules.ParentPin
import kotlinx.serialization.SerializationException
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertFalse
import org.junit.jupiter.api.Assertions.assertNull
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.assertThrows

class ContractCodecTest {

    private val snapshot = StateSnapshot(
        ts = 1787315400000,
        fw = "0.1.0",
        screenOn = true,
        locked = false,
        appId = "com.netflix.ninja",
        appName = "Netflix",
        usedTodaySeconds = 4210,
        remainingTodaySeconds = 1190,
        bonusTodaySeconds = 900,
        perApp = mapOf("com.netflix.ninja" to 610, "com.google.android.youtube.tv" to 3600),
        activeWindow = "weekday_afternoon",
        rulesRev = 7,
    )

    @Test
    fun `state survives a round trip`() {
        assertEquals(snapshot, ContractCodec.decodeState(ContractCodec.encode(snapshot)))
    }

    /**
     * The wire format is a contract with the Home Assistant integration, so the field names
     * are asserted literally. Renaming a Kotlin property must not silently rename a key.
     */
    @Test
    fun `state uses the documented field names`() {
        val keys = (Json.parseToJsonElement(ContractCodec.encode(snapshot)) as JsonObject).keys
        assertEquals(
            setOf(
                "schema", "ts", "fw", "screen_on", "locked", "app_id", "app_name",
                "used_today_s", "limit_today_s", "remaining_today_s", "bonus_today_s", "per_app",
                "per_app_names",
                "active_window", "lock_reason", "until_s", "rules_rev", "exempt_apps",
                "launchable_apps",
                "can_overlay", "can_usage", "pin_set",
                "pin_changed_at", "pin_changed_by",
            ),
            keys,
        )
    }

    /**
     * #102. An allow-list built out of [StateSnapshot.perApp] can only refuse apps the television
     * has already run, and that is never the app somebody wants refused.
     */
    @Test
    fun `what could be opened travels apart from what was watched`() {
        val withCatalogue = snapshot.copy(
            launchableApps = mapOf("com.disney.disneyplus" to "Disney+", "com.netflix.ninja" to "Netflix"),
        )
        val decoded = ContractCodec.decodeState(ContractCodec.encode(withCatalogue))

        assertEquals("Disney+", decoded.launchableApps["com.disney.disneyplus"])
        // Never opened, so no amount of reading per_app would have found it.
        assertFalse("com.disney.disneyplus" in decoded.perApp)
    }

    @Test
    fun `no limit is null and not zero`() {
        val unlimited = snapshot.copy(remainingTodaySeconds = null)
        val encoded = ContractCodec.encode(unlimited)

        assertTrue(encoded.contains("\"remaining_today_s\":null"), encoded)
        assertNull(ContractCodec.decodeState(encoded).remainingTodaySeconds)
    }

    @Test
    fun `an added field does not break an older reader`() {
        val withExtra = ContractCodec.encode(snapshot).dropLast(1) + ""","something_new":42}"""
        assertEquals(snapshot, ContractCodec.decodeState(withExtra))
    }

    @Test
    fun `a newer schema is refused rather than guessed`() {
        val fromTheFuture = ContractCodec.encode(snapshot)
            .replace("\"schema\":${Contract.SCHEMA_VERSION}", "\"schema\":${Contract.SCHEMA_VERSION + 1}")

        val thrown = assertThrows<UnsupportedSchemaException> { ContractCodec.decodeState(fromTheFuture) }
        assertEquals(Contract.SCHEMA_VERSION + 1, thrown.found)
    }

    @Test
    fun `a payload without a schema is read as the current one`() {
        val handWritten = """{"ts":1,"fw":"x","screen_on":false,"locked":true}"""
        val decoded = ContractCodec.decodeState(handWritten)

        assertEquals(Contract.SCHEMA_VERSION, decoded.schema)
        assertTrue(decoded.locked)
    }

    @Test
    fun `every command survives a round trip`() {
        val commands = listOf(
            Command.Lock("bedtime"),
            Command.Lock(),
            Command.Unlock(30),
            Command.Unlock(),
            Command.Grant(requestId = "8f14e45f", minutes = 15),
            Command.Deny(requestId = "8f14e45f"),
            Command.SetRules(rev = 8, rules = buildJsonObject { put("daily_limit_min", 60) }),
            Command.SetPin(ParentPin.create("4829", "0f1e2d3c4b5a69788796a5b4c3d2e1f0", 1000)),
            Command.SetPin(null),
            Command.StopApp("com.google.android.youtube.tv"),
            Command.Ping,
        )

        commands.forEach { command ->
            val encoded = ContractCodec.encode(command)
            assertEquals(command, ContractCodec.decodeCommand(encoded), encoded)
        }
    }

    @Test
    fun `commands are discriminated by op, as documented`() {
        assertTrue(ContractCodec.encode(Command.Lock("bedtime")).contains("\"op\":\"lock\""))
        assertTrue(ContractCodec.encode(Command.Ping).contains("\"op\":\"ping\""))
        assertTrue(
            ContractCodec.encode(Command.Grant("abc", 15)).contains("\"req_id\":\"abc\""),
        )
    }

    @Test
    fun `the PIN hash uses the documented field names`() {
        // Home Assistant hashes the PIN and sends the result, so these three keys are the only
        // thing making the two languages agree on what was derived. A Kotlin rename here is a
        // parent locked out of their own television.
        val encoded = ContractCodec.encode(
            Command.SetPin(ParentPin.create("4829", "0f1e2d3c4b5a69788796a5b4c3d2e1f0", 1000)),
        )

        assertTrue(encoded.contains("\"op\":\"set_pin\""), encoded)
        assertTrue(encoded.contains("\"iterations\":1000"), encoded)
        assertTrue(encoded.contains("\"salt\":\"0f1e2d3c4b5a69788796a5b4c3d2e1f0\""), encoded)
        assertTrue(encoded.contains("\"hash\":\""), encoded)
        assertFalse(encoded.contains("4829"), "the PIN itself is on the wire")
    }

    @Test
    fun `removing the PIN says so, rather than leaving the key out`() {
        assertEquals(
            """{"op":"set_pin","hash":null}""",
            ContractCodec.encode(Command.SetPin(null)),
        )

        // A truncated or hand-written command must not be read as "remove the PIN": that
        // failure would be silent, and would leave the television with nothing on it.
        assertThrows<SerializationException> {
            ContractCodec.decodeCommand("""{"op":"set_pin"}""")
        }
    }

    @Test
    fun `an unknown command is rejected, not silently ignored`() {
        assertThrows<SerializationException> {
            ContractCodec.decodeCommand("""{"op":"factory_reset"}""")
        }
    }

    @Test
    fun `a time request keeps its documented shape`() {
        val request = TimeRequest(
            id = "8f14e45f",
            appId = "com.netflix.ninja",
            askedMinutes = 15,
            ts = 1787315400000,
        )
        val encoded = ContractCodec.encode(request)

        assertTrue(encoded.contains("\"kind\":\"more_time\""), encoded)
        assertTrue(encoded.contains("\"asked_minutes\":15"), encoded)
        assertEquals(request, ContractCodec.decodeRequest(encoded))
    }
}
