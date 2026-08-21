/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.rules.pairing

import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertFalse
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test
import kotlin.random.Random

class PairingSessionTest {

    private val now = 1_787_000_000_000L

    private fun session(pin: String = "123456", validForMs: Long = 60_000, maxAttempts: Int = 5) =
        PairingSession(pin, expiresAtMs = now + validForMs, maxAttempts = maxAttempts)

    @Test
    fun `the right pin is accepted`() {
        assertEquals(PairingResult.Accepted, session().verify("123456", now))
    }

    @Test
    fun `a wrong pin costs an attempt and says how many are left`() {
        val subject = session(maxAttempts = 3)

        assertEquals(PairingResult.WrongPin(2), subject.verify("000000", now))
        assertEquals(PairingResult.WrongPin(1), subject.verify("000001", now))
        assertEquals(PairingResult.WrongPin(0), subject.verify("000002", now))
        assertEquals(PairingResult.NoAttemptsLeft, subject.verify("000003", now))
    }

    /** Otherwise a brute-forcer could keep a dead session usable by hammering it. */
    @Test
    fun `the correct pin no longer works once attempts run out`() {
        val subject = session(maxAttempts = 1)
        subject.verify("999999", now)

        assertEquals(PairingResult.NoAttemptsLeft, subject.verify("123456", now))
    }

    @Test
    fun `an expired session refuses even the right pin`() {
        val subject = session(validForMs = 60_000)
        assertEquals(PairingResult.Expired, subject.verify("123456", now + 60_000))
    }

    @Test
    fun `expiry is exclusive at the boundary`() {
        val subject = session(validForMs = 60_000)

        assertFalse(subject.isExpired(now + 59_999))
        assertTrue(subject.isExpired(now + 60_000))
    }

    /** Expiry must not consume an attempt; a caller could otherwise burn them all off-window. */
    @Test
    fun `a failed attempt after expiry does not consume an attempt`() {
        val subject = session(validForMs = 1_000, maxAttempts = 5)
        subject.verify("000000", now + 5_000)

        assertEquals(5, subject.attemptsRemaining)
    }

    /** A captured request replayed later must not pair a second time. */
    @Test
    fun `a session is spent after success`() {
        val subject = session()
        assertEquals(PairingResult.Accepted, subject.verify("123456", now))
        assertEquals(PairingResult.AlreadyUsed, subject.verify("123456", now))
    }

    @Test
    fun `a pin of the wrong length is simply wrong`() {
        val subject = session()

        assertEquals(PairingResult.WrongPin(4), subject.verify("12345", now))
        assertEquals(PairingResult.WrongPin(3), subject.verify("1234567", now))
        assertEquals(PairingResult.WrongPin(2), subject.verify("", now))
    }

    @Test
    fun `countdown reaches zero and does not go negative`() {
        val subject = session(validForMs = 30_000)

        assertEquals(30, subject.secondsRemaining(now))
        assertEquals(15, subject.secondsRemaining(now + 15_000))
        assertEquals(0, subject.secondsRemaining(now + 30_000))
        assertEquals(0, subject.secondsRemaining(now + 90_000))
    }

    @Test
    fun `a generated pin has the documented shape`() {
        val subject = PairingSession.create(now, Random(seed = 42))

        assertEquals(PairingSession.PIN_LENGTH, subject.pin.length)
        assertTrue(subject.pin.all { it.isDigit() }, subject.pin)
        assertEquals(PairingResult.Accepted, subject.verify(subject.pin, now))
    }

    @Test
    fun `generated pins are not all the same`() {
        val pins = (1..50).map { seed ->
            PairingSession.create(now, Random(seed = seed)).pin
        }
        assertTrue(pins.distinct().size > 1, "expected varied pins, got $pins")
    }
}
