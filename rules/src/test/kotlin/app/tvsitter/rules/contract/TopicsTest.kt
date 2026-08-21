/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.rules.contract

import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.assertThrows

class TopicsTest {

    @Test
    fun `derives the four topics from a prefix`() {
        val topics = Topics("tvsitter/livingroom")

        assertEquals("tvsitter/livingroom/availability", topics.availability)
        assertEquals("tvsitter/livingroom/state", topics.state)
        assertEquals("tvsitter/livingroom/request", topics.request)
        assertEquals("tvsitter/livingroom/cmd", topics.command)
    }

    @Test
    fun `stray whitespace and slashes are trimmed`() {
        assertEquals(Topics("tvsitter/livingroom"), Topics("  /tvsitter/livingroom/  "))
    }

    /**
     * A wildcard here would mean subscribing to other devices' topics and publishing
     * commands into unknown places, so it fails at construction rather than later.
     */
    @Test
    fun `wildcards are rejected`() {
        assertThrows<IllegalArgumentException> { Topics("tvsitter/+") }
        assertThrows<IllegalArgumentException> { Topics("tvsitter/#") }
        assertThrows<IllegalArgumentException> { Topics("tv+sitter/room") }
    }

    @Test
    fun `an empty prefix is rejected`() {
        assertThrows<IllegalArgumentException> { Topics("") }
        assertThrows<IllegalArgumentException> { Topics("   ") }
        assertThrows<IllegalArgumentException> { Topics("///") }
    }
}
