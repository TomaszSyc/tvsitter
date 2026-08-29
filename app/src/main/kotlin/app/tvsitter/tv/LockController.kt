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
    private val displacer: Displacer = Displacer(
        context,
        onSentHome = { if (overlay.isShowing) audio.claim() },
        onFight = { onFight?.invoke() },
    )
    private val audio: AudioFocusHold = AudioFocusHold(context) { if (overlay.isShowing) displacer.sendHome() }
    private val memory = LockMemory(context)

    /** The same list the counter uses to decide that standby is not watching (D20). */
    private val screenSavers = ScreenSaverPackages(context)
    private val settingsApps = SettingsPackages(context)

    private var state = LockState()

    /**
     * When viewing is allowed again, for a lock the hours put up. Null for every other reason.
     *
     * Kept beside the state rather than in it: the state machine compares decisions to decide
     * whether anything changed, and a clock time drifting from "16:00" to "16:00" would be the
     * same decision anyway. This is only ever read when the screen is being covered.
     */
    private var opensAt: LocalTime? = null

    /** Set after construction, like the requester's. Counting is somebody else's interest. */
    var tally: DayTally? = null

    /**
     * Somebody is working the source key against the lock, which this side cannot refuse —
     * the key never reaches the app, so a switch can only be undone. Set after construction
     * for the same reason as the tally: it is an alarm somebody else raises.
     */
    var onFight: (() -> Unit)? = null

    /**
     * Whether Settings is being kept out of reach right now.
     *
     * Asked rather than held, because it is a rule and rules change under us. Set after
     * construction like the other two, for the same reason.
     */
    var settingsBlocked: () -> Boolean = { false }

    /** Turns a package into something a child would recognise. Set after construction. */
    var appName: (String) -> String = { it }

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
     * When the television locks itself tonight, epoch millis, or zero for never.
     *
     * Read by the counter on every sample and handed to the engine, which turns it into the
     * same thing every rule turns into: how long until viewing has to stop. That is where the
     * warnings and the countdown come from, rather than from a second copy here.
     */
    var sleepAtMs: Long
        get() = memory.sleepAtMs
        set(value) {
            memory.sleepAtMs = value
        }

    /** Arms tonight's deadline, or cancels one already set. Zero and less both cancel. */
    fun sleepIn(minutes: Int) {
        if (minutes > 0) {
            sleepAtMs = System.currentTimeMillis() + minutes * MILLIS_PER_MINUTE
            Log.i(EnforcerService.TAG, "sleep timer: locking in ${minutes}m")
        } else {
            sleepAtMs = 0
            Log.i(EnforcerService.TAG, "sleep timer: off")
        }
    }

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
     * What the lock is calling itself, or null when it is not up.
     *
     * The same words the child is reading on the lock screen at that moment, rather than a
     * second wording of the same fact: the setup screen saying "the television is locked" while
     * the lock screen says "bedtime" is two answers to one question (#110).
     */
    val lockTitle: String? get() =
        if (overlay.isShowing) context.lockTitleFor(state.cause, state.lastDecision?.reason) else null

    /**
     * Tells the child something, wherever they can currently see it.
     *
     * On the lock screen it is the second line. Once the lock has gone it is the banner, which
     * matters for the case that reads worst otherwise: a grant lifts the lock, so a message
     * written on the lock screen would vanish in the same instant it appeared, and the child
     * would be left guessing whether anybody had answered at all.
     *
     * [onlyIfCovered] is for a number that goes stale rather than for news: with the lock up it
     * is one line among several the child is already reading, and with the lock down it is a
     * banner over the programme. The countdown on an unanswered question used to take the
     * second road every fifteen seconds for ten minutes — forty banners to keep one figure
     * honest, and somebody watching called it what it was.
     */
    fun say(message: String, onlyIfCovered: Boolean = false) {
        if (overlay.isShowing) {
            overlay.show(
                title = context.lockTitleFor(state.cause, state.lastDecision?.reason),
                subtitle = message,
                onAskForTime = onAskForTime,
                onEnterPin = if (pin.isSet) enterPin else null,
            )
        } else if (!onlyIfCovered) {
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
        if (memory.sleepAtMs > 0) sleepIn(0)
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
        // A deadline already past keeps saying zero, so a lock lifted without clearing it would
        // return on the next sample. Whoever lifts it has answered the bedtime too.
        if (memory.sleepAtMs > 0) sleepIn(0)
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
        if (packageName == null) return

        // Before the lock check, and deliberately: this one applies whether or not the screen
        // is covered. Behind a lock, Settings already lasts under a second; with no lock up it
        // lasted all day, and that is when a child would go looking for Force stop (D30).
        if (settingsBlocked() && settingsApps.contains(packageName)) {
            Log.i(EnforcerService.TAG, "settings: blocked, sending the TV home")
            displacer.sendHome()
            return
        }

        if (!overlay.isShowing) return
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
        if (warning != null) {
            banner.show(context.warningFor(warning, state.lastDecision?.reason))
        } else {
            banner.hide()
        }

        effects.displace?.let { app ->
            Log.i(EnforcerService.TAG, "rules: $app has used its own time, sending the TV home")
            displacer.sendHome()
            // Said out loud, because from the sofa an app closed itself for no reason and the
            // obvious move is to open it again — whose only answer was another trip home (#97).
            banner.show(context.getString(R.string.app_out_of_time, appName(app)))
        }
    }

    private fun show(reason: String?) {
        val wasShowing = overlay.isShowing
        // Before the overlay, not after: the point is that the sound stops when the screen is
        // covered, not a moment later.
        audio.claim()
        overlay.show(
            title = context.lockTitleFor(state.cause, state.lastDecision?.reason),
            // A child told only that the television is off has a fact and no way to plan around
            // it. Every reason that has an answer to "until when" gives it.
            subtitle = reason ?: context.untilWhen(state.cause, state.lastDecision?.reason, opensAt),
            onAskForTime = onAskForTime,
            onEnterPin = if (pin.isSet) enterPin else null,
        )
        if (!wasShowing) {
            handler.removeCallbacks(sweep)
            handler.post(sweep)
            tally?.recordLock()
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
        const val MILLIS_PER_MINUTE = 60_000L
    }
}

/**
 * How the warning reads, kept at file level so the controller holds only behaviour.
 *
 * Rounded up and never below one: "one minute left" with thirty seconds to go is friendlier
 * than "zero minutes left", and closer to what somebody would actually say.
 */
private fun Context.warningFor(remainingSeconds: Long?, reason: LockReason?): String {
    val minutes = remainingSeconds
        ?.let { ceil(it / SECONDS_IN_A_MINUTE).toInt() }
        ?.coerceAtLeast(1)
        ?: 1
    // "Minutes of television left" is wrong when it is one app's own budget running out with
    // hours left in the day, and a child who believes it is about to be surprised twice.
    val plural = if (reason == LockReason.APP_LIMIT) {
        R.plurals.warn_minutes_left_app
    } else {
        R.plurals.warn_minutes_left
    }
    return resources.getQuantityString(plural, minutes, minutes)
}

/**
 * What the lock calls itself, which is not always the end of the day.
 *
 * At file level so the controller holds behaviour rather than wording, and shared by both places
 * that put the overlay up — a message arriving during an out-of-hours lock must not re-title the
 * screen "that is it for today".
 */
internal fun Context.lockTitleFor(cause: LockCause, reason: LockReason?): String = getString(
    when {
        // A parent's decision outranks whatever the rules were saying at the time, and "that is
        // it for today" is simply untrue at four in the afternoon.
        cause == LockCause.MANUAL -> R.string.lock_title_manual
        reason == LockReason.OUTSIDE_WINDOW -> R.string.lock_title_hours
        reason == LockReason.SLEEP_TIMER -> R.string.lock_title_bedtime
        else -> R.string.lock_title
    },
)

/**
 * When the television comes back, for the reasons that have an answer.
 *
 * The hours know the time. A spent day knows it is tomorrow. A parent's lock and a bedtime know
 * neither — one ends when the parent says so and the other is the end of the evening — so they
 * say nothing rather than guessing, which is better than a promise the television cannot keep.
 */
private fun Context.untilWhen(cause: LockCause, reason: LockReason?, opensAt: LocalTime?): String? = when {
    cause == LockCause.MANUAL -> null
    reason == LockReason.OUTSIDE_WINDOW ->
        opensAt?.let { getString(R.string.lock_until_window, it.format(HOUR_AND_MINUTE)) }
    reason == LockReason.DAILY_LIMIT -> getString(R.string.lock_until_tomorrow)
    else -> null
}

private val HOUR_AND_MINUTE: DateTimeFormatter = DateTimeFormatter.ofPattern("HH:mm")

private const val SECONDS_IN_A_MINUTE = 60.0
