/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.rules

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import java.security.SecureRandom
import java.security.spec.KeySpec
import javax.crypto.SecretKeyFactory
import javax.crypto.spec.PBEKeySpec

/**
 * A stored parent PIN: never the PIN itself.
 *
 * Anyone with ADB can read this app's storage, and the point of the PIN is to survive a
 * curious child who has watched a setup video. The parameters travel with the hash so that
 * raising the iteration count later does not invalidate what is already stored.
 *
 * Serialisable because this crosses the wire: Home Assistant hashes a new PIN and sends the
 * result, so the PIN itself never reaches MQTT. That makes the field names part of the
 * contract, unlike the rules object, whose shape the transport is deliberately ignorant of —
 * here the two languages have to derive the same bytes, and nothing else checks that they do.
 */
@Serializable
data class PinHash(
    val iterations: Int,
    @SerialName("salt") val saltHex: String,
    @SerialName("hash") val hashHex: String,
) {
    /**
     * The digest is left out, because this reaches logcat.
     *
     * `mqtt: command $command` printed the whole thing when a PIN arrived from Home
     * Assistant, and a logcat pasted into a bug report is then a hash somebody can attack
     * offline at their leisure. The salt stays: on its own it is not worth attacking, and it
     * is what tells two stored hashes apart when somebody asks why their PIN stopped working.
     */
    override fun toString(): String = "PinHash(iterations=$iterations, salt=$saltHex, hash=…)"
}

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
     * Exactly four, which is what every television does and what makes the keypad work.
     *
     * A range would be more flexible and would cost the thing that matters more: entry can
     * only submit itself when the length is known, and on the screen that *sets* a PIN it
     * never is. So a range means a confirm button on every keypad for ever, and the platform's
     * own PIN screens do not have one.
     *
     * Four digits is ten thousand candidates, which the lockout in [PinGuard] — five tries,
     * then a wait that grows — turns into more than a month of relentless guessing.
     */
    const val LENGTH: Int = 4

    const val ALGORITHM: String = "PBKDF2WithHmacSHA256"

    /**
     * Available from API 26, which is this project's floor, so no fallback to SHA-1 is needed.
     * The count is a compromise: high enough to be worth doing, low enough that a television's
     * processor answers a PIN entry without a visible pause.
     */
    const val ITERATIONS: Int = 120_000

    /**
     * A ceiling on the iteration count, because it arrives over MQTT.
     *
     * The derivation runs on the main thread of the app holding the lock up, so a payload
     * asking for a billion iterations would not be a stronger PIN, it would be a keypad that
     * stops answering. Anything above this is treated as malformed rather than obeyed.
     */
    const val MAX_ITERATIONS: Int = 1_000_000

    private const val KEY_LENGTH_BITS = 256

    /** Sixteen bytes, which is the common recommendation and more than a PIN needs. */
    private const val SALT_BYTES = 16

    fun isPlausible(pin: String): Boolean = pin.length == LENGTH && pin.all { it.isDigit() }

    /**
     * Whether a stored hash is well formed enough to compare against.
     *
     * Checked rather than assumed because a hash arrives from Home Assistant over MQTT, and
     * anything on that topic can be hand-written. An empty or odd-length salt throws inside
     * `PBEKeySpec`, and that throw would happen on the main thread of the service holding the
     * lock up — taking the lock down with it. A malformed hash is refused on arrival and, if
     * one is already stored, read as though there were no PIN at all.
     */
    fun isUsable(stored: PinHash): Boolean = stored.iterations in 1..MAX_ITERATIONS &&
        stored.saltHex.length >= 2 &&
        stored.saltHex.length % 2 == 0 &&
        stored.saltHex.all { it.isHexDigit() } &&
        stored.hashHex.isNotEmpty() &&
        stored.hashHex.all { it.isHexDigit() }

    fun randomSaltHex(random: SecureRandom = SecureRandom()): String =
        ByteArray(SALT_BYTES).also(random::nextBytes).toHexString()

    /**
     * Hashes [pin] under a fresh salt, ready to be stored.
     *
     * The salt is a parameter rather than always generated here so that a test can pin the
     * result; in use, the default is what callers want.
     */
    fun create(pin: String, saltHex: String = randomSaltHex(), iterations: Int = ITERATIONS): PinHash {
        // Not an assertion about the keypad, which cannot produce anything else. It is about
        // the other caller: a PIN arriving from Home Assistant is hashed there, but one
        // arriving from anywhere else must not be stored unchecked.
        require(isPlausible(pin)) { "a PIN is $LENGTH digits" }
        return PinHash(iterations, saltHex, hash(pin, saltHex, iterations))
    }

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

    /** Whether [pin] is the one behind [stored]. False for a hash that cannot be compared. */
    fun matches(pin: String, stored: PinHash): Boolean {
        if (!isUsable(stored)) return false
        return constantTimeEquals(hash(pin, stored.saltHex, stored.iterations), stored.hashHex)
    }

    private fun Char.isHexDigit(): Boolean = this in '0'..'9' || this in 'a'..'f' || this in 'A'..'F'

    private fun String.hexToByteArray(): ByteArray {
        require(length % 2 == 0) { "a hex string has an even number of characters" }
        return ByteArray(length / 2) { index ->
            substring(index * 2, index * 2 + 2).toInt(radix = HEX_RADIX).toByte()
        }
    }

    private fun ByteArray.toHexString(): String = joinToString(separator = "") { byte -> "%02x".format(byte) }

    private const val HEX_RADIX = 16
}
