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
    private val send: (TimeRequest) -> Unit,
    private val onGranted: (Long) -> Unit,
    private val say: (String) -> Unit,
) {
    private var history = RequestHistory()
    private var scope: CoroutineScope? = null
    private val handler = Handler(Looper.getMainLooper())
    private val giveUp = Runnable { expireIfDue() }

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

        when (val verdict = result.verdict) {
            is AskVerdict.Allowed -> {
                send(
                    TimeRequest(
                        id = verdict.request.id,
                        appId = currentApp(),
                        askedMinutes = verdict.request.askedMinutes,
                        ts = nowMs,
                    ),
                )
                Log.i(EnforcerService.TAG, "request ${verdict.request.id} sent")
                say(context.getString(R.string.request_sent))
                scheduleGiveUp(verdict.request)
            }

            is AskVerdict.AlreadyWaiting -> say(context.getString(R.string.request_waiting))
            is AskVerdict.TooSoon -> say(waitMessage(verdict.secondsRemaining))
            is AskVerdict.TooMany -> say(waitMessage(verdict.secondsRemaining))
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
                onGranted(answer.minutes * SECONDS_PER_MINUTE)
                say(minutesMessage(R.plurals.request_granted, answer.minutes))
            }

            Answer.Refused -> {
                handler.removeCallbacks(giveUp)
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
        scope = null
    }

    private fun expireIfDue() {
        val result = RequestPolicy.expireIfDue(history, System.currentTimeMillis()) ?: return
        history = result.history
        persist()
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

    private fun waitMessage(seconds: Long): String = minutesMessage(R.plurals.request_wait, minutesFrom(seconds))

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
        const val ID_LENGTH = 8
    }
}
