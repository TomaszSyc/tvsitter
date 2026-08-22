/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.rules

import java.security.spec.KeySpec
import javax.crypto.SecretKeyFactory
import javax.crypto.spec.PBEKeySpec

/**
 * A stored parent PIN: never the PIN itself.
 *
 * Anyone with ADB can read this app's storage, and the point of the PIN is to survive a
 * curious child who has watched a setup video. The parameters travel with the hash so that
 * raising the iteration count later does not invalidate what is already stored.
 */
data class PinHash(val iterations: Int, val saltHex: String, val hashHex: String)

/**
 * Hashing and checking the PIN a parent types on the TV to lift a lock by hand.
 *
 * Deliberately not `PairingSession`, despite both dealing in PINs. That one is a single
 * window: it expires, it is spent by one success, and it holds the PIN in memory in the clear
 * because the PIN is on the screen anyway. This one is long-lived, never sees the PIN twice,
 * and answers failures with a timed lockout rather than permanent exhaustion. What the two
 * genuinely share is [constantTimeEquals] and the discipline of checking state before
 * consuming an attempt; the rest would have been a false economy to force together.
 *
 * What hashing does and does not buy, since it is easy to overstate. It stops the PIN being
 * read straight out of a file by somebody poking around with ADB. It does not make a
 * four-digit secret safe against an offline attack: ten thousand candidates at this iteration
 * count is minutes of work for anyone who has the file and wants to. The control that
 * actually protects the PIN is the on-device lockout in [PinGuard], and the reason to hash is
 * that a stolen file should not hand over a PIN the parent may have used elsewhere.
 */
object ParentPin {

    /**
     * Four is what people expect of a TV; more than eight is unkind on a D-pad, where every
     * digit is several presses.
     */
    const val MIN_LENGTH: Int = 4
    const val MAX_LENGTH: Int = 8

    const val ALGORITHM: String = "PBKDF2WithHmacSHA256"

    /**
     * Available from API 26, which is this project's floor, so no fallback to SHA-1 is needed.
     * The count is a compromise: high enough to be worth doing, low enough that a television's
     * processor answers a PIN entry without a visible pause.
     */
    const val ITERATIONS: Int = 120_000

    private const val KEY_LENGTH_BITS = 256

    fun isPlausible(pin: String): Boolean = pin.length in MIN_LENGTH..MAX_LENGTH && pin.all { it.isDigit() }

    /** Derives the hash for [pin] with the given salt, as lowercase hex. */
    fun hash(pin: String, saltHex: String, iterations: Int = ITERATIONS): String {
        val spec: KeySpec = PBEKeySpec(
            pin.toCharArray(),
            saltHex.hexToByteArray(),
            iterations,
            KEY_LENGTH_BITS,
        )
        val derived = SecretKeyFactory.getInstance(ALGORITHM).generateSecret(spec).encoded
        return derived.toHexString()
    }

    /** Whether [pin] is the one behind [stored]. */
    fun matches(pin: String, stored: PinHash): Boolean =
        constantTimeEquals(hash(pin, stored.saltHex, stored.iterations), stored.hashHex)

    private fun String.hexToByteArray(): ByteArray {
        require(length % 2 == 0) { "a hex string has an even number of characters" }
        return ByteArray(length / 2) { index ->
            substring(index * 2, index * 2 + 2).toInt(radix = HEX_RADIX).toByte()
        }
    }

    private fun ByteArray.toHexString(): String = joinToString(separator = "") { byte -> "%02x".format(byte) }

    private const val HEX_RADIX = 16
}
