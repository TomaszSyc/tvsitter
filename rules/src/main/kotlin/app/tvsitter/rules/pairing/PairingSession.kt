/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.rules.pairing

import kotlin.random.Random

/** What happened when someone presented a PIN. */
sealed interface PairingResult {
    /** The PIN matched. The session is spent and will refuse everything afterwards. */
    data object Accepted : PairingResult

    data class WrongPin(val attemptsRemaining: Int) : PairingResult

    data object Expired : PairingResult

    data object NoAttemptsLeft : PairingResult

    /** The session was already used, so a replayed request must not succeed again. */
    data object AlreadyUsed : PairingResult
}

/**
 * One pairing window: a PIN shown on the TV, valid briefly and for a few attempts.
 *
 * The PIN is what makes pairing safe — possessing it means standing in front of the TV,
 * the same assumption the rest of the product rests on. Which is why it expires and why
 * guesses are counted: a six-digit code on a home network is otherwise brute-forceable at
 * leisure, and a code left on an idle screen for a week is not a secret.
 *
 * Pure logic, no Android, so the awkward parts — expiry boundaries, attempt exhaustion,
 * replay — are testable without a device.
 */
class PairingSession(val pin: String, private val expiresAtMs: Long, maxAttempts: Int = DEFAULT_MAX_ATTEMPTS) {
    private var attemptsLeft: Int = maxAttempts
    private var used: Boolean = false

    val attemptsRemaining: Int get() = attemptsLeft

    fun isExpired(nowMs: Long): Boolean = nowMs >= expiresAtMs

    fun secondsRemaining(nowMs: Long): Long = ((expiresAtMs - nowMs).coerceAtLeast(0)) / MILLIS_PER_SECOND

    /**
     * Checks a presented PIN. Order matters: a spent or expired session must not consume
     * an attempt, or a caller could keep a dead session alive by hammering it.
     */
    fun verify(candidate: String, nowMs: Long): PairingResult = when {
        used -> PairingResult.AlreadyUsed
        isExpired(nowMs) -> PairingResult.Expired
        attemptsLeft <= 0 -> PairingResult.NoAttemptsLeft
        constantTimeEquals(candidate, pin) -> {
            used = true
            PairingResult.Accepted
        }
        else -> {
            attemptsLeft -= 1
            PairingResult.WrongPin(attemptsLeft)
        }
    }

    /**
     * Compares without leaking where the mismatch is through timing. The length is public
     * anyway — it is printed on the screen — so only the digits get this treatment.
     */
    private fun constantTimeEquals(a: String, b: String): Boolean {
        if (a.length != b.length) return false
        var difference = 0
        for (index in a.indices) {
            difference = difference or (a[index].code xor b[index].code)
        }
        return difference == 0
    }

    companion object {
        const val DEFAULT_MAX_ATTEMPTS: Int = 5
        const val DEFAULT_VALID_FOR_MS: Long = 5 * 60 * 1000
        const val PIN_LENGTH: Int = 6

        private const val MILLIS_PER_SECOND = 1000L
        private const val DIGIT_BOUND = 10

        /**
         * Generates a session. [random] is injected so tests are deterministic; production
         * passes a cryptographically strong source.
         */
        fun create(
            nowMs: Long,
            random: Random,
            validForMs: Long = DEFAULT_VALID_FOR_MS,
            maxAttempts: Int = DEFAULT_MAX_ATTEMPTS,
        ): PairingSession {
            val pin = (1..PIN_LENGTH)
                .map { random.nextInt(0, DIGIT_BOUND) }
                .joinToString(separator = "")
            return PairingSession(pin, nowMs + validForMs, maxAttempts)
        }
    }
}
