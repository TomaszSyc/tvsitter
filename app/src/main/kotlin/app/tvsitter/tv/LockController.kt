/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.tv

import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Handler
import android.os.Looper
import android.util.Log
import app.tvsitter.rules.BudgetVerdict
import app.tvsitter.rules.PinOutcome
import kotlin.math.ceil

/**
 * What is on the screen, and why.
 *
 * The lock has two possible reasons and they behave differently. A budget lock lifts by itself
 * when there is time again — because a bonus was granted, or the day rolled over. A lock a
 * parent asked for stays until a parent lifts it. Without keeping them apart, granting fifteen
 * minutes would also undo a deliberate lock, and unlocking by hand would be reversed by the
 * next sample ten seconds later.
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
    private val audio = AudioFocusHold(context) { displaceWhateverIsPlaying() }
    private val memory = LockMemory(context)

    private var lockedManually = false
    private var lockedByBudget = false
    private var lastVerdict: BudgetVerdict? = null
    private var lastDisplacedAtMs = 0L

    private val handler = Handler(Looper.getMainLooper())
    private val displaceAgain = Runnable { displaceWhateverIsPlaying() }

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

    /** Resolved once. Sending the home screen home would be a fight with nobody. */
    private val homePackage: String? by lazy {
        val home = Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_HOME)
        context.packageManager
            .resolveActivity(home, PackageManager.MATCH_DEFAULT_ONLY)
            ?.activityInfo
            ?.packageName
    }

    val isLocked: Boolean get() = overlay.isShowing

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
                title = context.getString(R.string.lock_title),
                subtitle = message,
                onAskForTime = onAskForTime,
                onEnterPin = if (pin.isSet) ::promptForPin else null,
            )
        } else {
            banner.show(message)
        }
    }

    fun lockManually(reason: String?) {
        lockedManually = true
        memory.cause = LockCause.MANUAL
        show(reason)
    }

    /**
     * Puts the lock straight back after a reboot, before storage is readable.
     *
     * The cause matters, not just the fact: restored as a budget lock it lifts as soon as
     * there is time again, and restored as a manual one it stays until a parent lifts it.
     * Without the distinction, the first verdict after startup would undo a lock somebody
     * deliberately put up.
     */
    fun restoreFromMemory() {
        when (memory.cause) {
            LockCause.MANUAL -> {
                lockedManually = true
                Log.i(EnforcerService.TAG, "lock restored from before the reboot: manual")
                show(null)
            }

            LockCause.BUDGET -> {
                lockedByBudget = true
                Log.i(EnforcerService.TAG, "lock restored from before the reboot: budget")
                show(null)
            }

            LockCause.NONE -> Unit
        }
    }

    /**
     * Lifts a lock a parent asked for.
     *
     * Does not lift a budget lock: the overlay would come straight back on the next sample and
     * look broken. Granting time is how that one is answered, which is why `unlock` carrying
     * minutes means something different from `unlock` on its own.
     */
    fun unlockManually() {
        lockedManually = false
        if (lockedByBudget) {
            Log.i(EnforcerService.TAG, "unlock ignored: the budget is spent, grant time instead")
            return
        }
        hide()
    }

    /**
     * Acts on what the budget says, but only when the answer has changed.
     *
     * Sampling runs every ten seconds and the verdict is usually the same as last time.
     * Re-showing the warning on each one would put a banner on screen permanently for the last
     * five minutes of the day, which is nagging rather than warning.
     */
    fun applyVerdict(verdict: BudgetVerdict, remainingSeconds: Int?) {
        if (verdict == lastVerdict) return
        lastVerdict = verdict

        if (verdict == BudgetVerdict.SPENT) {
            lockedByBudget = true
            if (!lockedManually) memory.cause = LockCause.BUDGET
            banner.hide()
            // No subtitle: the title already says the day is done, and a reason that
            // repeats it prints the same sentence twice.
            show(null)
            return
        }

        // Anything that is not SPENT means there is time, so a budget lock has to lift —
        // including WARN. Treating WARN as merely "show a banner" left the lock up after a
        // grant of a few minutes: there was time again, a warning about it was on screen, and
        // the television stayed covered.
        lockedByBudget = false
        if (!lockedManually) hide()

        if (verdict == BudgetVerdict.WARN) {
            banner.show(warningFor(remainingSeconds))
        } else {
            banner.hide()
        }
    }

    /**
     * Offers the keypad, which is the way out of the lock with no Home Assistant in reach.
     *
     * Only ever reached from a button that exists when there is a PIN, so an entry here is a
     * parent's attempt rather than a way of finding out whether a PIN exists at all.
     */
    private fun promptForPin() {
        overlay.showKeypad(context.getString(R.string.pin_enter), ::onPinTyped)
    }

    /**
     * Answers the keypad twice: once immediately, and once when the hash has been derived.
     *
     * The derivation takes about two seconds on this television, so the first answer is only
     * "checking". Without it the keypad sits there having apparently swallowed the press.
     */
    private fun onPinTyped(typed: String): String? {
        pin.verify(typed) { outcome ->
            if (outcome == PinOutcome.Accepted) {
                unlockUntilReset()
            } else {
                overlay.keypadMessage(context.pinMessage(outcome).orEmpty())
            }
        }
        return context.getString(R.string.pin_checking)
    }

    /**
     * Lifts the lock, setting the limit aside only when the limit is what put it there.
     *
     * The answer both to `unlock` with no minutes and to a correct PIN, which have to mean the
     * same thing. Setting the limit aside either way meant that lifting a bedtime lock also
     * handed over the rest of the day's budget, which is not what the person doing it asked
     * for (#42). Hiding a budget lock *without* setting the limit aside does not work either:
     * the next sample would put it straight back, ten seconds later, for no reason a child
     * could be told.
     */
    fun unlockUntilReset() {
        if (lockedByBudget) onLimitStandDown()
        unlockManually()
    }

    /**
     * Sends the television to its own home screen, which is the only thing that silences a
     * source audio focus cannot reach.
     *
     * An HDMI input is an ordinary activity here (D12), so bringing the launcher forward puts
     * it in the background — and that does stop the sound. Confirmed by ear, because `dumpsys
     * audio` goes on reporting the input service's track as started either way and is no use
     * as evidence.
     *
     * Two things ask for this. Audio focus being taken back is the fast one, at about eighty
     * milliseconds, and it catches something that keeps playing without coming to the front.
     * Anything arriving in front of the lock is the thorough one, at up to a poll interval,
     * and it catches what the first misses — measured on this set, `KEYCODE_TV` brings the
     * HDMI input back from behind the lock without touching audio focus at all, and the remote
     * has app hotkeys that presumably do the same.
     *
     * Rate-limited rather than once per lock. Once per lock meant a single press of the source
     * key defeated it for good; a cooldown means the television always gets the last word
     * without two processes taking turns.
     *
     * An app that pauses when it loses focus never reaches any of this, which matters: dropping
     * a child out of a film loses their place, and doing that unnecessarily is rude.
     */
    fun onForegroundApp(packageName: String?) {
        if (!overlay.isShowing || packageName == null) return
        // Our own screens are windows on this overlay rather than activities, so anything of
        // ours in front is the setup screen a parent opened deliberately.
        if (packageName == context.packageName || packageName == homePackage) return

        Log.i(EnforcerService.TAG, "lock: $packageName came forward behind the lock")
        displaceWhateverIsPlaying()
    }

    private fun displaceWhateverIsPlaying() {
        if (!overlay.isShowing) return

        val nowMs = System.currentTimeMillis()
        val since = nowMs - lastDisplacedAtMs
        if (since < DISPLACE_COOLDOWN_MS) {
            // Deferred rather than dropped. Dropping it lost: pressing the source key twice
            // inside the cooldown left the console in front, because the second request went
            // in the bin and nothing else was ever going to arrive. Measured, and it worked.
            handler.removeCallbacks(displaceAgain)
            handler.postDelayed(displaceAgain, DISPLACE_COOLDOWN_MS - since)
            return
        }
        lastDisplacedAtMs = nowMs

        val home = Intent(Intent.ACTION_MAIN)
            .addCategory(Intent.CATEGORY_HOME)
            .setFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        val started = runCatching { context.startActivity(home) }
        if (started.isFailure) {
            // Starting an activity from the background is restricted, and the app-op behind
            // the lock window is what exempts us. If that were ever revoked, this is where it
            // would show up rather than as sound that quietly never stops.
            Log.e(
                EnforcerService.TAG,
                "audio: could not reach the home screen",
                started.exceptionOrNull(),
            )
            return
        }
        Log.i(EnforcerService.TAG, "audio: sent the TV home to stop what focus could not")
        // The launcher plays previews of its own and, unlike an HDMI input, does respect
        // focus — so it is worth asking for it again now that we are the ones in front.
        audio.claim()
    }

    fun stop() {
        handler.removeCallbacks(sweep)
        handler.removeCallbacks(displaceAgain)
        banner.hide()
        overlay.hide()
        audio.release()
    }

    private fun warningFor(remainingSeconds: Int?): String {
        // Rounded up, and never below one: "one minute left" while thirty seconds remain is
        // friendlier than "zero minutes left", and closer to what somebody would say.
        val minutes = remainingSeconds
            ?.let { ceil(it / SECONDS_PER_MINUTE).toInt() }
            ?.coerceAtLeast(1)
            ?: 1
        return context.resources.getQuantityString(R.plurals.warn_minutes_left, minutes, minutes)
    }

    private fun show(reason: String?) {
        val wasShowing = overlay.isShowing
        // Before the overlay, not after: the point is that the sound stops when the screen is
        // covered, not a moment later.
        audio.claim()
        overlay.show(
            title = context.getString(R.string.lock_title),
            subtitle = reason,
            onAskForTime = onAskForTime,
            onEnterPin = if (pin.isSet) ::promptForPin else null,
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
        handler.removeCallbacks(displaceAgain)
        memory.cause = LockCause.NONE
        overlay.hide()
        // Given back, so the television is exactly as usable as it was. Nothing resumes by
        // itself, which is deliberate — see AudioFocusHold.
        audio.release()
        onChanged()
    }

    private companion object {
        const val SECONDS_PER_MINUTE = 60.0

        /**
         * Long enough that a stubborn app cannot turn this into a tight loop, short enough
         * that pressing the source key buys a couple of seconds of console and no more.
         * Requests arriving inside it are deferred to its end rather than dropped, so the
         * television always gets the last word.
         */
        const val DISPLACE_COOLDOWN_MS = 2_000L

        /** How often the lock asks what is in front of it. */
        const val SWEEP_INTERVAL_MS = 2_000L
    }
}
