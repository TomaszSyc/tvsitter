/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.rules

import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertFalse
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test

class ParentPinTest {

    private val salt = "0f1e2d3c4b5a69788796a5b4c3d2e1f0"

    @Test
    fun `the hash agrees with what Python computes`() {
        // Generated with hashlib.pbkdf2_hmac("sha256", b"482913", salt, iterations). The two
        // halves of this product hash in different languages, so the vector is the contract:
        // a PIN set from Home Assistant has to verify on the TV, and nothing else checks that.
        assertEquals(
            "8de25825f30eff014f53eb11cb0ac52aceadce257d18fac740e3342a13e87ef3",
            ParentPin.hash("482913", salt, iterations = 1000),
        )
        assertEquals(
            "9734df1754755f353cb4f019e4eaaf441b1cc2b826fd45f7f378469e791cb8d0",
            ParentPin.hash("482913", salt, iterations = 120_000),
        )
    }

    @Test
    fun `the right PIN matches and a near miss does not`() {
        val stored = PinHash(
            iterations = 1000,
            saltHex = salt,
            hashHex = ParentPin.hash("482913", salt, iterations = 1000),
        )

        assertTrue(ParentPin.matches("482913", stored))
        assertFalse(ParentPin.matches("482914", stored))
        assertFalse(ParentPin.matches("48291", stored))
        assertFalse(ParentPin.matches("", stored))
    }

    @Test
    fun `the same PIN under a different salt hashes differently`() {
        // Which is the point of the salt: two households with the same PIN must not share a
        // hash, or one leak tells you about the other.
        val other = "ffffffffffffffffffffffffffffffff"

        assertFalse(
            ParentPin.hash("482913", salt, 1000) == ParentPin.hash("482913", other, 1000),
        )
    }

    @Test
    fun `the parameters travel with the hash so they can be raised later`() {
        val old = PinHash(1000, salt, ParentPin.hash("482913", salt, 1000))
        val new = PinHash(120_000, salt, ParentPin.hash("482913", salt, 120_000))

        // An old hash keeps verifying after the default goes up, rather than locking a parent
        // out of their own television on an upgrade.
        assertTrue(ParentPin.matches("482913", old))
        assertTrue(ParentPin.matches("482913", new))
    }

    @Test
    fun `only plausible PINs are accepted for setting`() {
        assertTrue(ParentPin.isPlausible("1234"))
        assertTrue(ParentPin.isPlausible("12345678"))
        assertFalse(ParentPin.isPlausible("123"), "too short to be worth having")
        assertFalse(ParentPin.isPlausible("123456789"), "unkind on a D-pad")
        assertFalse(ParentPin.isPlausible("12a4"), "a keypad only produces digits")
        assertFalse(ParentPin.isPlausible(""))
    }
}
