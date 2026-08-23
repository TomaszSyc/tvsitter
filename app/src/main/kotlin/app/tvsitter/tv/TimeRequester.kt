/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.tv

import android.content.Context
import android.os.Handler
import android.os.Looper
import android.util.Log
import app.tvsitter.rules.Answer
import app.tvsitter.rules.AskVerdict
import app.tvsitter.rules.RequestHistory
import app.tvsitter.rules.RequestPolicy
import app.tvsitter.rules.contract.TimeRequest
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.launch
import java.util.UUID
import kotlin.math.ceil

/**
 * Asking a parent for more time, on the device.
 *
 * The decisions — may the child ask, does this answer count, has the question expired — are
 * all in [RequestPolicy] and tested on the JVM. What is here is everything Android-shaped:
 * generating an id, persisting the history, putting the question on the broker, and telling
 * the child on screen what happened to it.
 *
 * The last of those is the point. A button that sends something into the dark and says nothing
 * is a button a child presses again, and again, which is exactly what the allowance is there
 * to stop. So every path says something: asked, already asked, not yet, too many, granted,
 * refused, nobody answered.
 */
class TimeRequester(
    private val context: Context,
    private val currentApp: () -> String?,
    private val currentAppName: () -> String?,
    private val send: (TimeRequest) -> Unit,
    private val onGranted: (Long) -> Unit,
    private val say: (String) -> Unit,
) {
    /** What the screen is currently counting down to, if anything. */
    private enum class Waiting { NONE, ANSWER, ALLOWANCE }

    private var history = RequestHistory()
    private var scope: CoroutineScope? = null
    private val handler = Handler(Looper.getMainLooper())
    private val giveUp = Runnable { expireIfDue() }

    private var waitingFor = Waiting.NONE
    private var waitingUntilMs = 0L

    /**
     * Re-says the message while there is something to count down to.
     *
     * A number worked out once and left on screen goes stale, and the only way a child can
     * refresh it is to press the button again — which is exactly what the allowance is there
     * to discourage. Every fifteen seconds keeps a minute-granular figure honest.
     */
    private val tick = object : Runnable {
        override fun run() {
            if (waitingFor == Waiting.NONE) return
            val remaining = waitingUntilMs - System.currentTimeMillis()
            if (remaining <= 0) {
                stopWaiting(announce = waitingFor == Waiting.ALLOWANCE)
                return
            }
            say(waitingMessage(remaining))
            handler.postDelayed(this, TICK_MS)
        }
    }

    fun start(scope: CoroutineScope) {
        this.scope = scope
        scope.launch {
            history = Settings(context).requests()
            Log.i(
                EnforcerService.TAG,
                "requests restored: pending=${history.pending?.id} asked=${history.askedAtMs.size}",
            )
            // A question left outstanding when the process died is given up on here, rather
            // than sitting there claiming to be waiting for an answer that is not coming.
            expireIfDue()
            history.pending?.let(::scheduleGiveUp)
        }
    }

    /** The child pressed the button on the lock screen. */
    fun ask() {
        val nowMs = System.currentTimeMillis()
        val result = RequestPolicy.ask(history, newId(), ASK_MINUTES, nowMs)
        history = result.history
        persist()

        // Every verdict, not only the ones that go out. Without this a refusal looks
        // exactly like a dead button from outside — which is how twenty minutes went on
        // deciding whether a press had arrived at all.
        Log.i(EnforcerService.TAG, "request: ${result.verdict}")

        when (val verdict = result.verdict) {
            is AskVerdict.Allowed -> {
                startWaiting(Waiting.ANSWER, nowMs + RequestPolicy.EXPIRY_MS)
                send(
                    TimeRequest(
                        id = verdict.request.id,
                        appId = currentApp(),
                        appName = currentAppName(),
                        askedMinutes = verdict.request.askedMinutes,
                        ts = nowMs,
                    ),
                )
                Log.i(EnforcerService.TAG, "request ${verdict.request.id} sent")
                say(context.getString(R.string.request_sent))
                scheduleGiveUp(verdict.request)
            }

            is AskVerdict.AlreadyWaiting -> startWaiting(
                Waiting.ANSWER,
                nowMs + verdict.secondsRemaining * MILLIS_PER_SECOND,
            )

            is AskVerdict.TooSoon ->
                startWaiting(Waiting.ALLOWANCE, nowMs + verdict.secondsRemaining * MILLIS_PER_SECOND)

            is AskVerdict.TooMany ->
                startWaiting(Waiting.ALLOWANCE, nowMs + verdict.secondsRemaining * MILLIS_PER_SECOND)
        }
    }

    /** A parent answered. [minutes] null is a refusal. */
    fun settle(id: String, minutes: Int?) {
        val nowMs = System.currentTimeMillis()
        val result = minutes
            ?.let { RequestPolicy.grant(history, id, it) }
            ?: RequestPolicy.refuse(history, id, nowMs)
        history = result.history
        persist()

        when (val answer = result.answer) {
            is Answer.Granted -> {
                handler.removeCallbacks(giveUp)
                stopWaiting(announce = false)
                onGranted(answer.minutes * SECONDS_PER_MINUTE)
                say(minutesMessage(R.plurals.request_granted, answer.minutes))
            }

            Answer.Refused -> {
                handler.removeCallbacks(giveUp)
                stopWaiting(announce = false)
                say(context.getString(R.string.request_refused))
            }

            // Nothing on screen for either: one is an answer to a question that is already
            // over, the other is addressed to a television that never asked.
            Answer.AlreadySettled, Answer.Unknown, Answer.Expired ->
                Log.i(EnforcerService.TAG, "request $id: $answer")
        }
    }

    fun stop() {
        handler.removeCallbacks(giveUp)
        handler.removeCallbacks(tick)
        scope = null
    }

    /** Puts a countdown on screen and keeps it moving. */
    private fun startWaiting(kind: Waiting, untilMs: Long) {
        waitingFor = kind
        waitingUntilMs = untilMs
        handler.removeCallbacks(tick)
        handler.post(tick)
    }

    private fun stopWaiting(announce: Boolean) {
        waitingFor = Waiting.NONE
        waitingUntilMs = 0
        handler.removeCallbacks(tick)
        // Only the allowance running out is worth saying out loud. A question giving up
        // already has its own message, and saying both would contradict itself.
        if (announce) say(context.getString(R.string.request_can_ask))
    }

    private fun waitingMessage(remainingMs: Long): String {
        val minutes = minutesFrom(remainingMs / MILLIS_PER_SECOND)
        val plural = when (waitingFor) {
            Waiting.ALLOWANCE -> R.plurals.request_wait
            else -> R.plurals.request_waiting_minutes
        }
        return minutesMessage(plural, minutes)
    }

    private fun expireIfDue() {
        val result = RequestPolicy.expireIfDue(history, System.currentTimeMillis()) ?: return
        history = result.history
        persist()
        stopWaiting(announce = false)
        Log.i(EnforcerService.TAG, "request expired with no answer")
        say(context.getString(R.string.request_expired))
    }

    private fun scheduleGiveUp(request: app.tvsitter.rules.PendingRequest) {
        handler.removeCallbacks(giveUp)
        val remaining = request.askedAtMs + RequestPolicy.EXPIRY_MS - System.currentTimeMillis()
        handler.postDelayed(giveUp, remaining.coerceAtLeast(0))
    }

    private fun persist() {
        val snapshot = history
        scope?.launch {
            runCatching { Settings(context).saveRequests(snapshot) }
                .onFailure { Log.w(EnforcerService.TAG, "requests: could not persist", it) }
        }
    }

    /**
     * A fresh id per question, eight hex characters as the contract's example shows.
     *
     * Random rather than a counter: an answer carries the id, and a counter restarting at one
     * after a reinstall would let an old answer settle a new question.
     */
    private fun newId(): String = UUID.randomUUID().toString().take(ID_LENGTH)

    private fun minutesMessage(plural: Int, minutes: Int): String =
        context.resources.getQuantityString(plural, minutes, minutes)

    /** Rounded up and never zero: "wait 0 minutes" in front of a button that refuses is worse. */
    private fun minutesFrom(seconds: Long): Int = ceil(seconds / SECONDS_PER_MINUTE.toDouble()).toInt().coerceAtLeast(1)

    private companion object {
        /**
         * What the child asks for. Not a choice on screen: the parent decides the number, and
         * a child picking it turns one button into a negotiation before anybody has answered.
         */
        const val ASK_MINUTES = 15

        const val SECONDS_PER_MINUTE = 60L
        const val MILLIS_PER_SECOND = 1_000L
        const val ID_LENGTH = 8

        /** Often enough that a minute-granular countdown is never more than this stale. */
        const val TICK_MS = 15_000L
    }
}
