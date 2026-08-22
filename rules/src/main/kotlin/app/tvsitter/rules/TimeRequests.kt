/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.rules

import kotlinx.serialization.Serializable

/** A request the child has made and the television is still waiting on an answer to. */
@Serializable
data class PendingRequest(val id: String, val askedMinutes: Int, val askedAtMs: Long)

/**
 * What the television remembers about asking for time.
 *
 * Returned rather than held, so the caller persists it. Without persistence, force-stopping
 * the app resets the allowance and the cooldown — and force-stopping an app is something a
 * child can do from Settings. The same reasoning as the PIN lockout in [PinGuard].
 */
@Serializable
data class RequestHistory(
    /** When each allowed request was made, within the sliding window. */
    val askedAtMs: List<Long> = emptyList(),
    /** When a parent last said no, which starts the cooldown. Zero for never. */
    val refusedAtMs: Long = 0,
    val pending: PendingRequest? = null,
    /** Ids that have been answered. A second answer to one of these changes nothing. */
    val settled: List<String> = emptyList(),
    /** Ids nobody answered in time. A late answer to one of these is still honoured. */
    val lapsed: List<String> = emptyList(),
)

/** Whether the child may ask right now. */
sealed interface AskVerdict {
    data class Allowed(val request: PendingRequest) : AskVerdict

    /** Already waiting on an answer, with how long before that request gives up. */
    data class AlreadyWaiting(val request: PendingRequest, val secondsRemaining: Long) : AskVerdict

    /** A parent said no recently. */
    data class TooSoon(val secondsRemaining: Long) : AskVerdict

    /** The allowance for the hour is spent, with how long until it is not. */
    data class TooMany(val secondsRemaining: Long) : AskVerdict
}

/** What became of a request. */
sealed interface Answer {
    data class Granted(val minutes: Int) : Answer

    data object Refused : Answer

    /** Nobody answered in time, so the screen stops saying "waiting". */
    data object Expired : Answer

    /** An answer to a request that has already been answered. Deliberately nothing. */
    data object AlreadySettled : Answer

    /** An answer to a request this television has never made. */
    data object Unknown : Answer
}

data class AskResult(val verdict: AskVerdict, val history: RequestHistory)

data class AnswerResult(val answer: Answer, val history: RequestHistory)

/**
 * When the child may ask for more time, and what happens to a request afterwards.
 *
 * A button a child can press forty times is a button that teaches a parent to swipe the
 * notification away without reading it, and then the feature is worse than not having it. So
 * there is an allowance per hour, a cooldown after a refusal, and an expiry for a question
 * nobody answered — that last one so the television stops claiming to be waiting when it is
 * not, which is the state a child would otherwise sit in front of all evening.
 *
 * Every decision is a function of the history and the clock, so all of it is tested on the
 * JVM. What is not here: generating the id, which needs a random source, and persistence.
 */
object RequestPolicy {

    /** Three an hour. Enough for a real negotiation, not enough to be a game. */
    const val MAX_PER_HOUR: Int = 3

    const val WINDOW_MS: Long = 60 * 60 * 1000

    /**
     * Fifteen minutes after a no.
     *
     * A refusal is an answer, and asking again immediately is how a child turns one into a
     * negotiation. Long enough to mean something, short enough that a change of mind — "after
     * this episode" — is not blocked for the evening.
     */
    const val COOLDOWN_AFTER_REFUSAL_MS: Long = 15 * 60 * 1000

    /**
     * Ten minutes to answer.
     *
     * Matched by the notification's own timeout, so a question that has stopped being asked
     * also stops being answerable from the phone.
     */
    const val EXPIRY_MS: Long = 10 * 60 * 1000

    /** Enough to cover a parent tapping twice, and not a list that grows all evening. */
    const val REMEMBERED_IDS: Int = 8

    private const val MILLIS_PER_SECOND = 1000L

    fun ask(history: RequestHistory, id: String, askedMinutes: Int, nowMs: Long): AskResult {
        val waiting = history.pending
        if (waiting != null) {
            val remaining = waiting.askedAtMs + EXPIRY_MS - nowMs
            if (remaining > 0) {
                // Not counted against the allowance: pressing the button twice is one
                // question, and charging for the second press would spend an evening's
                // allowance on impatience.
                return AskResult(
                    AskVerdict.AlreadyWaiting(waiting, secondsUp(remaining)),
                    history,
                )
            }
        }

        // Anything past its expiry is cleared here as well as by expireIfDue, so a request
        // nobody answered cannot block asking again just because nothing sampled in between.
        val cleared = if (waiting != null) lapse(history, waiting) else history

        val cooldown = cleared.refusedAtMs + COOLDOWN_AFTER_REFUSAL_MS - nowMs
        if (cleared.refusedAtMs > 0 && cooldown > 0) {
            return AskResult(AskVerdict.TooSoon(secondsUp(cooldown)), cleared)
        }

        val recent = cleared.askedAtMs.filter { nowMs - it < WINDOW_MS }
        val withinWindow = cleared.copy(askedAtMs = recent)
        if (recent.size >= MAX_PER_HOUR) {
            // Until the oldest of them drops out of the window, which is when there is room
            // for one more — not the full hour from now.
            val oldest = recent.min()
            return AskResult(
                AskVerdict.TooMany(secondsUp(oldest + WINDOW_MS - nowMs)),
                withinWindow,
            )
        }

        val request = PendingRequest(id, askedMinutes, nowMs)
        return AskResult(
            AskVerdict.Allowed(request),
            withinWindow.copy(pending = request, askedAtMs = recent + nowMs),
        )
    }

    /**
     * A parent granted [minutes].
     *
     * A grant for a request that expired is still honoured. The alternative — ignoring it —
     * means a parent taps "+15" and nothing happens anywhere, which is the worse of the two
     * failures: the duplicate protection exists so that two taps do not grant twice, not to
     * enforce punctuality on the person being generous.
     *
     * No clock, unlike [refuse]: nothing about granting depends on when it happened. A
     * refusal starts a cooldown, so that one does.
     */
    fun grant(history: RequestHistory, id: String, minutes: Int): AnswerResult = when {
        history.pending?.id == id -> AnswerResult(Answer.Granted(minutes), settle(history, id))
        id in history.lapsed -> AnswerResult(Answer.Granted(minutes), settle(history, id))
        id in history.settled -> AnswerResult(Answer.AlreadySettled, history)
        else -> AnswerResult(Answer.Unknown, history)
    }

    /** A parent said no, which starts the cooldown. */
    fun refuse(history: RequestHistory, id: String, nowMs: Long): AnswerResult = when {
        history.pending?.id == id || id in history.lapsed ->
            AnswerResult(Answer.Refused, settle(history, id).copy(refusedAtMs = nowMs))

        id in history.settled -> AnswerResult(Answer.AlreadySettled, history)
        else -> AnswerResult(Answer.Unknown, history)
    }

    /**
     * Gives up on a question nobody answered, so the screen can stop saying "waiting".
     *
     * Returns a null answer when there is nothing to give up on, which is the ordinary case
     * on every sample.
     */
    fun expireIfDue(history: RequestHistory, nowMs: Long): AnswerResult? {
        val waiting = history.pending ?: return null
        if (nowMs - waiting.askedAtMs < EXPIRY_MS) return null
        return AnswerResult(Answer.Expired, lapse(history, waiting))
    }

    private fun settle(history: RequestHistory, id: String): RequestHistory = history.copy(
        pending = if (history.pending?.id == id) null else history.pending,
        settled = remember(history.settled, id),
        lapsed = history.lapsed - id,
    )

    private fun lapse(history: RequestHistory, waiting: PendingRequest): RequestHistory =
        history.copy(pending = null, lapsed = remember(history.lapsed, waiting.id))

    /** Most recent first, and bounded: this is for a parent tapping twice, not an archive. */
    private fun remember(ids: List<String>, id: String): List<String> = (listOf(id) + (ids - id)).take(REMEMBERED_IDS)

    private fun secondsUp(millis: Long): Long = (millis + MILLIS_PER_SECOND - 1) / MILLIS_PER_SECOND
}
