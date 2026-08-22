/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.rules

import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertNull
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test

class RequestPolicyTest {

    private val now = 1_787_400_000_000
    private val minute = 60_000L

    /** Asks [count] times, a minute apart, and hands back where that leaves things. */
    private fun asked(count: Int, from: Long = now): RequestHistory {
        var history = RequestHistory()
        repeat(count) { index ->
            val at = from + index * minute
            history = RequestPolicy.ask(history, "req$index", 15, at).history
            // Answered, so the next ask is not simply "already waiting".
            history = RequestPolicy.grant(history, "req$index", 15).history
        }
        return history
    }

    @Test
    fun `the first request is allowed`() {
        val result = RequestPolicy.ask(RequestHistory(), "abc", 15, now)

        assertTrue(result.verdict is AskVerdict.Allowed, "${result.verdict}")
        assertEquals(PendingRequest("abc", 15, now), result.history.pending)
    }

    @Test
    fun `pressing the button twice is one question`() {
        val first = RequestPolicy.ask(RequestHistory(), "abc", 15, now)
        val second = RequestPolicy.ask(first.history, "def", 15, now + 2000)

        val waiting = second.verdict as AskVerdict.AlreadyWaiting
        assertEquals("abc", waiting.request.id)
        // Not counted against the allowance: charging for impatience would spend an
        // evening's worth of asking on one question.
        assertEquals(1, second.history.askedAtMs.size)
        assertEquals("abc", second.history.pending?.id)
    }

    @Test
    fun `the allowance runs out and says how long to wait`() {
        val history = asked(RequestPolicy.MAX_PER_HOUR)

        val refused = RequestPolicy.ask(history, "one-too-many", 15, now + 5 * minute)

        val tooMany = refused.verdict as AskVerdict.TooMany
        // Until the oldest of the three drops out of the window, not a full hour from now.
        assertEquals((RequestPolicy.WINDOW_MS - 5 * minute) / 1000, tooMany.secondsRemaining)
        assertNull(refused.history.pending)
    }

    @Test
    fun `the window slides, so the allowance comes back`() {
        val history = asked(RequestPolicy.MAX_PER_HOUR)

        // Past the last of the three, so nothing is left inside the window.
        val wellAfter = now + RequestPolicy.WINDOW_MS + RequestPolicy.MAX_PER_HOUR * minute
        val later = RequestPolicy.ask(history, "fresh", 15, wellAfter)

        assertTrue(later.verdict is AskVerdict.Allowed, "${later.verdict}")
        assertEquals(1, later.history.askedAtMs.size, "the old timestamps were kept")
    }

    @Test
    fun `the window slides one request at a time`() {
        // The three asks were a minute apart, so an hour after the first only that one has
        // dropped out. One more is allowed, and then it is full again.
        val history = asked(RequestPolicy.MAX_PER_HOUR)
        val justAfterTheOldest = now + RequestPolicy.WINDOW_MS + 1

        val room = RequestPolicy.ask(history, "fourth", 15, justAfterTheOldest)
        assertTrue(room.verdict is AskVerdict.Allowed, "${room.verdict}")
        assertEquals(RequestPolicy.MAX_PER_HOUR, room.history.askedAtMs.size)

        val settled = RequestPolicy.grant(room.history, "fourth", 15).history
        val full = RequestPolicy.ask(settled, "fifth", 15, justAfterTheOldest)
        assertTrue(full.verdict is AskVerdict.TooMany, "${full.verdict}")
    }

    @Test
    fun `a refusal starts a cooldown`() {
        val asked = RequestPolicy.ask(RequestHistory(), "abc", 15, now)
        val refused = RequestPolicy.refuse(asked.history, "abc", now + minute)

        assertEquals(Answer.Refused, refused.answer)

        val tooSoon = RequestPolicy.ask(refused.history, "def", 15, now + 2 * minute)
        val verdict = tooSoon.verdict as AskVerdict.TooSoon
        assertEquals((RequestPolicy.COOLDOWN_AFTER_REFUSAL_MS - minute) / 1000, verdict.secondsRemaining)
    }

    @Test
    fun `the cooldown runs out`() {
        val asked = RequestPolicy.ask(RequestHistory(), "abc", 15, now)
        val refused = RequestPolicy.refuse(asked.history, "abc", now).history

        val after = RequestPolicy.ask(refused, "def", 15, now + RequestPolicy.COOLDOWN_AFTER_REFUSAL_MS)

        assertTrue(after.verdict is AskVerdict.Allowed, "${after.verdict}")
    }

    @Test
    fun `a grant answers the request and clears it`() {
        val asked = RequestPolicy.ask(RequestHistory(), "abc", 15, now)

        val granted = RequestPolicy.grant(asked.history, "abc", 30)

        assertEquals(Answer.Granted(30), granted.answer)
        assertNull(granted.history.pending)
        assertTrue("abc" in granted.history.settled)
    }

    @Test
    fun `a parent tapping twice grants once`() {
        // What the contract promises, and the reason answered ids are remembered at all.
        val asked = RequestPolicy.ask(RequestHistory(), "abc", 15, now)
        val once = RequestPolicy.grant(asked.history, "abc", 15)

        val twice = RequestPolicy.grant(once.history, "abc", 15)

        assertEquals(Answer.AlreadySettled, twice.answer)
    }

    @Test
    fun `an answer to a request this television never made is ignored`() {
        val result = RequestPolicy.grant(RequestHistory(), "somebody-elses", 15)

        assertEquals(Answer.Unknown, result.answer)
        assertTrue(result.history.settled.isEmpty())
    }

    @Test
    fun `a question nobody answers stops being asked`() {
        val asked = RequestPolicy.ask(RequestHistory(), "abc", 15, now)

        assertNull(
            RequestPolicy.expireIfDue(asked.history, now + RequestPolicy.EXPIRY_MS - 1),
            "gave up early",
        )

        val expired = checkNotNull(
            RequestPolicy.expireIfDue(asked.history, now + RequestPolicy.EXPIRY_MS),
        )
        assertEquals(Answer.Expired, expired.answer)
        assertNull(expired.history.pending)
    }

    @Test
    fun `a late grant is still honoured`() {
        // A parent tapping "+15" must not do nothing at all, anywhere. The duplicate
        // protection is there so two taps grant once, not to be punctual about generosity.
        val asked = RequestPolicy.ask(RequestHistory(), "abc", 15, now)
        val expired = RequestPolicy.expireIfDue(asked.history, now + RequestPolicy.EXPIRY_MS)!!

        val late = RequestPolicy.grant(expired.history, "abc", 15)

        assertEquals(Answer.Granted(15), late.answer)
        assertTrue("abc" !in late.history.lapsed, "still answerable a second time")
    }

    @Test
    fun `asking again after an expiry does not need a sample in between`() {
        // expireIfDue runs on a timer, and the child may well press the button first.
        val asked = RequestPolicy.ask(RequestHistory(), "abc", 15, now)

        val again = RequestPolicy.ask(asked.history, "def", 15, now + RequestPolicy.EXPIRY_MS)

        assertTrue(again.verdict is AskVerdict.Allowed, "${again.verdict}")
        assertEquals("def", again.history.pending?.id)
        assertTrue("abc" in again.history.lapsed)
    }

    @Test
    fun `the remembered ids do not grow all evening`() {
        var history = RequestHistory()
        repeat(RequestPolicy.REMEMBERED_IDS * 2) { index ->
            val at = now + index * RequestPolicy.WINDOW_MS
            history = RequestPolicy.ask(history, "req$index", 15, at).history
            history = RequestPolicy.grant(history, "req$index", 15).history
        }

        assertEquals(RequestPolicy.REMEMBERED_IDS, history.settled.size)
        // Most recent first, so the ones a parent might still tap are the ones kept.
        assertEquals("req${RequestPolicy.REMEMBERED_IDS * 2 - 1}", history.settled.first())
    }
}
