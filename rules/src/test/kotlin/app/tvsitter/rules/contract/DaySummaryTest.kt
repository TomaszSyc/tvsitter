/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.rules.contract

import app.tvsitter.rules.BudgetState
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertNull
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test
import java.time.LocalDate

class DaySummaryTest {

    private val now = 1_787_400_000_000

    private val friday = BudgetState(
        day = LocalDate.parse("2026-08-28"),
        usedMillis = 5_400_000,
        bonusMillis = 900_000,
        perAppMillis = mapOf("com.netflix.ninja" to 3_600_000, "com.spotify.tv.android" to 60_000),
    )

    private val names = mapOf(
        "com.netflix.ninja" to "Netflix",
        "com.spotify.tv.android" to "Spotify",
        "com.google.android.youtube.tv" to "YouTube",
    )

    private val counters = DayCounters(
        requests = RequestTally(asked = 3, granted = 1, denied = 1, expired = 1),
        grantedSeconds = 900,
        lockCount = 2,
    )

    @Test
    fun `the day that closes is the one described, not the one starting`() {
        val summary = DaySummary.of(friday, 7_200, names, counters, now)

        assertEquals("2026-08-28", summary.day)
        assertEquals(5_400, summary.usedSeconds)
        assertEquals(900, summary.bonusSeconds)
        assertEquals(7_200, summary.limitSeconds)
    }

    @Test
    fun `only the apps that were watched are named`() {
        // The same rule the state payload follows: a list of everything installed is a
        // different thing, and one worth not sending.
        val summary = DaySummary.of(friday, null, names, counters, now)

        assertEquals(setOf("com.netflix.ninja", "com.spotify.tv.android"), summary.perAppNames.keys)
        assertEquals("Netflix", summary.perAppNames["com.netflix.ninja"])
    }

    @Test
    fun `a day with no limit says so rather than inventing one`() {
        // What was enforced, not what the rules said. A limit set aside at nine is a day with
        // no limit, and claiming one would make the total read as an overrun nobody allowed.
        val summary = DaySummary.of(friday, null, names, counters, now)

        assertNull(summary.limitSeconds)
    }

    @Test
    fun `what the counter cannot remember comes from the tally`() {
        // A refused request leaves nothing in the budget, and neither does a lock that went up
        // and came down again.
        val summary = DaySummary.of(friday, 7_200, names, counters, now)

        assertEquals(3, summary.requests.asked)
        assertEquals(1, summary.requests.denied)
        assertEquals(1, summary.requests.expired)
        assertEquals(900, summary.grantedSeconds)
        assertEquals(2, summary.lockCount)
    }

    @Test
    fun `a day nobody watched is still a day`() {
        val quiet = BudgetState(day = LocalDate.parse("2026-08-28"))

        val summary = DaySummary.of(quiet, 7_200, names, DayCounters(), now)

        assertEquals(0, summary.usedSeconds)
        assertTrue(summary.perApp.isEmpty())
        assertTrue(summary.perAppNames.isEmpty(), "and it names nobody")
        assertEquals(0, summary.requests.asked)
    }

    @Test
    fun `it survives the round trip it will make over MQTT`() {
        val summary = DaySummary.of(friday, 7_200, names, counters, now)

        val encoded = ContractCodec.encode(summary)

        assertEquals(summary, ContractCodec.decodeDay(encoded), encoded)
    }

    @Test
    fun `the day uses the documented field names`() {
        val encoded = ContractCodec.encode(DaySummary.of(friday, 7_200, names, counters, now))

        listOf("used_s", "limit_s", "bonus_s", "per_app", "per_app_names", "granted_s", "lock_count")
            .forEach { key -> assertTrue(encoded.contains("\"$key\""), "$key missing from $encoded") }
    }
}
