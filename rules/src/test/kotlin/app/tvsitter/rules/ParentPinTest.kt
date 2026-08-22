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
import org.junit.jupiter.api.assertThrows

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
    fun `a created hash verifies its own PIN at the current cost`() {
        val created = ParentPin.create("1357", salt)

        assertEquals(ParentPin.ITERATIONS, created.iterations)
        assertEquals(salt, created.saltHex)
        assertTrue(ParentPin.matches("1357", created))
        assertFalse(ParentPin.matches("1358", created))
    }

    @Test
    fun `a PIN that could not be typed is not stored either`() {
        assertThrows<IllegalArgumentException> { ParentPin.create("12", salt) }
        assertThrows<IllegalArgumentException> { ParentPin.create("12a4", salt) }
    }

    @Test
    fun `a fresh salt is full length and not the same twice`() {
        val first = ParentPin.randomSaltHex()
        val second = ParentPin.randomSaltHex()

        // Sixteen bytes as hex. A short salt would still be a salt, and would still be wrong.
        assertEquals(32, first.length)
        assertFalse(first == second, "two salts came out identical")
    }

    @Test
    fun `a hash that cannot be compared against is refused rather than thrown at`() {
        // These arrive over MQTT, where anything can be hand-written. An empty or odd-length
        // salt throws inside PBEKeySpec, and that throw would happen on the main thread of the
        // service holding the lock up.
        assertFalse(ParentPin.isUsable(PinHash(1000, "", "abcd")))
        assertFalse(ParentPin.isUsable(PinHash(1000, "0f1", "abcd")), "odd number of characters")
        assertFalse(ParentPin.isUsable(PinHash(1000, "zzzz", "abcd")), "not hex")
        assertFalse(ParentPin.isUsable(PinHash(1000, salt, "")))
        assertFalse(ParentPin.isUsable(PinHash(0, salt, "abcd")))
        assertFalse(ParentPin.isUsable(PinHash(-1, salt, "abcd")))
        assertTrue(ParentPin.isUsable(PinHash(1000, salt, "abcd")))
    }

    @Test
    fun `an iteration count nobody could wait for is not obeyed`() {
        // Not a stronger PIN, a keypad that stops answering: the derivation runs on the main
        // thread of the app drawing the lock.
        assertFalse(ParentPin.isUsable(PinHash(ParentPin.MAX_ITERATIONS + 1, salt, "abcd")))
        assertTrue(ParentPin.isUsable(PinHash(ParentPin.MAX_ITERATIONS, salt, "abcd")))
    }

    @Test
    fun `comparing against a malformed hash says no instead of throwing`() {
        assertFalse(ParentPin.matches("482913", PinHash(1000, "", "abcd")))
        assertFalse(ParentPin.matches("482913", PinHash(1000, "0f1", "abcd")))
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
