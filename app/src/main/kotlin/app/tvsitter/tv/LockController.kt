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
import app.tvsitter.rules.Judgement
import app.tvsitter.rules.LockCause
import app.tvsitter.rules.LockChange
import app.tvsitter.rules.LockReason
import app.tvsitter.rules.LockState
import app.tvsitter.rules.LockTransitions
import app.tvsitter.rules.PinOutcome
import java.time.LocalTime
import java.time.format.DateTimeFormatter
import kotlin.math.ceil

/**
 * What is on the screen, and why.
 *
 * The deciding is not here. [LockState] and [LockTransitions] hold it, in `:rules`, where it is
 * tested on the JVM — this class turns their answers into an overlay, a banner, audio focus and
 * two values in device-encrypted storage, and nothing else. Five bugs came out of this logic
 * while it lived in the fields of a service class that no test could reach (#43).
 *
 * The shape that makes that work: every entry point asks for a transition, then hands the result
 * to [act], which compares what was covered before against what should be covered now and only
 * touches the screen on the difference. Nothing here decides whether a lock stays.
 */
class LockController(
    private val context: Context,
    private val pin: PinKeeper,
    /** What is in front right now, asked repeatedly while the lock is up. */
    private val foregroundApp: () -> String?,
    private val onAskForTime: () -> Unit,
    private val onLimitStandDown: () -> Unit,
    private val onChanged: () -> Unit,
) {
    private val overlay = LockOverlay(context)
    private val banner = WarningBanner(context)

    // Types spelled out because these two refer to each other: the lock claims focus after
    // going home, and losing focus is one of the things that sends it home.
    private val displacer: Displacer = Displacer(context) { if (overlay.isShowing) audio.claim() }
    private val audio: AudioFocusHold = AudioFocusHold(context) { if (overlay.isShowing) displacer.sendHome() }
    private val memory = LockMemory(context)

    /** The same list the counter uses to decide that standby is not watching (D20). */
    private val screenSavers = ScreenSaverPackages(context)

    private var state = LockState()

    /**
     * When viewing is allowed again, for a lock the hours put up. Null for every other reason.
     *
     * Kept beside the state rather than in it: the state machine compares decisions to decide
     * whether anything changed, and a clock time drifting from "16:00" to "16:00" would be the
     * same decision anyway. This is only ever read when the screen is being covered.
     */
    private var opensAt: LocalTime? = null

    private val handler = Handler(Looper.getMainLooper())

    private val resumeManual = Runnable {
        act(LockTransitions.resumeAfterStandDown(state, System.currentTimeMillis()))
    }

    /**
     * Asks what is in front, over and over, for as long as the lock is up.
     *
     * Both of the other triggers are edges — focus taken back, foreground app changed — and an
     * edge cannot see a state that was already wrong. Measured: with the console already in
     * front and the focus already lost, pressing the source key changed nothing that anything
     * was watching, and the lock sat there over a playing console perfectly happily.
     */
    private val sweep = object : Runnable {
        override fun run() {
            if (!overlay.isShowing) return
            onForegroundApp(foregroundApp())
            handler.postDelayed(this, SWEEP_INTERVAL_MS)
        }
    }

    /**
     * Offers the keypad, which is the way out of the lock with no Home Assistant in reach.
     *
     * A value rather than a method because that is what it is used as — the overlay is handed
     * this to call — and because the deciding in this class is meant to be countable at a
     * glance rather than mixed in with its callbacks.
     */
    private val enterPin = { overlay.showKeypad(context.getString(R.string.pin_enter), onPinTyped) }

    /**
     * Answers the keypad twice: once immediately, and once when the hash has been derived.
     *
     * The derivation takes about two seconds on this television, so the first answer is only
     * "checking". Without it the keypad sits there having apparently swallowed the press.
     */
    private val onPinTyped: (String) -> String? = { typed ->
        pin.verify(typed) { outcome ->
            if (outcome == PinOutcome.Accepted) {
                unlockUntilReset()
            } else {
                overlay.keypadMessage(context.pinMessage(outcome).orEmpty())
            }
        }
        context.getString(R.string.pin_checking)
    }

    val isLocked: Boolean get() = overlay.isShowing

    /**
     * Why the screen is covered, in the words the contract uses, or null when it is not.
     *
     * A parent's own lock outranks whatever the rules were saying at the time: they asked for
     * it, and "the day's allowance is gone" would be an answer to a question nobody asked.
     */
    val lockReason: String? get() = when {
        !overlay.isShowing -> null
        state.cause == LockCause.MANUAL -> LockReason.MANUAL
        else -> state.lastDecision?.reason?.wire
    }

    /**
     * Tells the child something, wherever they can currently see it.
     *
     * On the lock screen it is the second line. Once the lock has gone it is the banner, which
     * matters for the case that reads worst otherwise: a grant lifts the lock, so a message
     * written on the lock screen would vanish in the same instant it appeared, and the child
     * would be left guessing whether anybody had answered at all.
     */
    fun say(message: String) {
        if (overlay.isShowing) {
            overlay.show(
                title = context.lockTitleFor(state.lastDecision?.reason),
                subtitle = message,
                onAskForTime = onAskForTime,
                onEnterPin = if (pin.isSet) enterPin else null,
            )
        } else {
            banner.show(message)
        }
    }

    fun lockManually(reason: String?) {
        act(LockTransitions.lockManually(state), reason)
    }

    /** A parent granted time, so a lock they put up stands down and comes back on its own. */
    fun standDownFor(seconds: Long) {
        Log.i(EnforcerService.TAG, "lock: standing down for ${seconds}s of granted time")
        act(LockTransitions.standDownFor(state, seconds, System.currentTimeMillis()))
    }

    /**
     * Puts the lock straight back after a reboot, from the little that is remembered.
     *
     * The cause matters, not just the fact: restored as a budget lock it lifts as soon as there
     * is time again, and restored as a manual one it stays until a parent lifts it.
     */
    fun restoreFromMemory() {
        val remembered = memory.cause
        if (remembered != LockCause.NONE) {
            Log.i(EnforcerService.TAG, "lock restored from before the reboot: $remembered")
        }
        act(LockTransitions.restore(remembered, memory.pausedUntilMs, System.currentTimeMillis()))
    }

    /** Lifts a lock a parent asked for, and not one the rules put up. */
    fun unlockManually() {
        if (state.budget) {
            Log.i(EnforcerService.TAG, "unlock ignored: the budget is spent, grant time instead")
        }
        act(LockTransitions.unlockManually(state, System.currentTimeMillis()))
    }

    /**
     * Lifts the lock, setting the limit aside only when the limit is what put it there.
     *
     * The answer both to `unlock` with no minutes and to a correct PIN, which have to mean the
     * same thing. Setting the limit aside either way meant that lifting a bedtime lock also
     * handed over the rest of the day's budget (#42).
     */
    fun unlockUntilReset() {
        act(LockTransitions.unlockUntilReset(state, System.currentTimeMillis()))
    }

    /** Acts on what the rules say. The deciding, including when to say nothing, is in `:rules`. */
    fun applyJudgement(judgement: Judgement) {
        opensAt = judgement.opensAt
        act(LockTransitions.applyDecision(state, judgement, System.currentTimeMillis()))
    }

    /**
     * Something came forward while the lock was up, so put the television back where it was.
     *
     * An app that pauses when it loses focus never reaches this, which matters: dropping a child
     * out of a film loses their place, and doing that unnecessarily is rude.
     */
    fun onForegroundApp(packageName: String?) {
        if (!overlay.isShowing || packageName == null) return
        // Our own screens are windows on this overlay rather than activities, so anything of
        // ours in front is the setup screen a parent opened deliberately.
        if (packageName == context.packageName || packageName == displacer.homePackage) return
        // A screen saver behind a lock is the television idling, not a child getting round it.
        // Sending it home dismissed the saver, which came straight back, and the two fought
        // every two seconds for as long as the lock was up — measured, #95. That kept the panel
        // awake all night and defeated the burn-in protection, on a set where that is already a
        // known problem (#50).
        if (screenSavers.contains(packageName)) return

        Log.i(EnforcerService.TAG, "lock: $packageName came forward behind the lock")
        displacer.sendHome()
    }

    fun stop() {
        handler.removeCallbacks(sweep)
        handler.removeCallbacks(resumeManual)
        displacer.stop()
        banner.hide()
        overlay.hide()
        audio.release()
    }

    /**
     * Carries out one transition: remembers it, schedules what it implies, and changes the
     * screen only where it differs from what was already there.
     *
     * Both values go to storage on every transition rather than at the places that used to
     * write them. That is what killed #66 and the same mistake one path along — a spent budget
     * arriving during granted time used to write BUDGET over a parent's decision, so a restart
     * restored a lock that lifted by itself.
     */
    private fun act(change: LockChange, reason: String? = null) {
        val nowMs = System.currentTimeMillis()
        val wasCovered = state.covered(nowMs)
        state = change.state
        memory.cause = state.cause
        memory.pausedUntilMs = state.pausedUntilMs

        handler.removeCallbacks(resumeManual)
        if (state.pausedUntilMs > nowMs) {
            handler.postDelayed(resumeManual, state.pausedUntilMs - nowMs)
        }

        val effects = change.effects ?: return
        if (effects.standDownLimit) onLimitStandDown()

        if (effects.covered != wasCovered) {
            Log.i(EnforcerService.TAG, "lock: ${if (effects.covered) "covered" else "clear"}, cause ${state.cause}")
            if (effects.covered) show(reason) else hide()
        }

        val warning = effects.warnAtRemainingSeconds
        if (warning != null) banner.show(context.warningFor(warning)) else banner.hide()

        effects.displace?.let { app ->
            Log.i(EnforcerService.TAG, "rules: $app has used its own time, sending the TV home")
            displacer.sendHome()
        }
    }

    private fun show(reason: String?) {
        val wasShowing = overlay.isShowing
        // Before the overlay, not after: the point is that the sound stops when the screen is
        // covered, not a moment later.
        audio.claim()
        val lockedByHours = state.lastDecision?.reason == LockReason.OUTSIDE_WINDOW
        overlay.show(
            title = context.lockTitleFor(state.lastDecision?.reason),
            // "Again at four" rather than nothing. A child told only that the television is off
            // has been given a fact and no way to plan around it, and "that is it for today" —
            // which is what this said before — is not even true when it is the hours.
            subtitle = reason ?: opensAt?.takeIf { lockedByHours }?.let {
                context.getString(R.string.lock_until_window, it.format(HOUR_AND_MINUTE))
            },
            onAskForTime = onAskForTime,
            onEnterPin = if (pin.isSet) enterPin else null,
        )
        if (!wasShowing) {
            handler.removeCallbacks(sweep)
            handler.post(sweep)
            onChanged()
        }
    }

    private fun hide() {
        if (!overlay.isShowing) return
        handler.removeCallbacks(sweep)
        displacer.stop()
        overlay.hide()
        // Given back, so the television is exactly as usable as it was. Nothing resumes by
        // itself, which is deliberate — see AudioFocusHold.
        audio.release()
        onChanged()
    }

    private companion object {
        /** How often the lock asks what is in front of it. */
        const val SWEEP_INTERVAL_MS = 2_000L
    }
}

/**
 * How the warning reads, kept at file level so the controller holds only behaviour.
 *
 * Rounded up and never below one: "one minute left" with thirty seconds to go is friendlier
 * than "zero minutes left", and closer to what somebody would actually say.
 */
private fun Context.warningFor(remainingSeconds: Long?): String {
    val minutes = remainingSeconds
        ?.let { ceil(it / SECONDS_IN_A_MINUTE).toInt() }
        ?.coerceAtLeast(1)
        ?: 1
    return resources.getQuantityString(R.plurals.warn_minutes_left, minutes, minutes)
}

/**
 * What the lock calls itself, which is not always the end of the day.
 *
 * At file level so the controller holds behaviour rather than wording, and shared by both places
 * that put the overlay up — a message arriving during an out-of-hours lock must not re-title the
 * screen "that is it for today".
 */
private fun Context.lockTitleFor(reason: LockReason?): String = getString(
    if (reason == LockReason.OUTSIDE_WINDOW) R.string.lock_title_hours else R.string.lock_title,
)

private val HOUR_AND_MINUTE: DateTimeFormatter = DateTimeFormatter.ofPattern("HH:mm")

private const val SECONDS_IN_A_MINUTE = 60.0
