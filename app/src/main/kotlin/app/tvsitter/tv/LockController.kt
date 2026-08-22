/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.tv

import android.content.Context
import android.util.Log
import app.tvsitter.rules.BudgetVerdict
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
    private val onAskForTime: () -> Unit,
    private val onChanged: () -> Unit,
) {
    private val overlay = LockOverlay(context)
    private val banner = WarningBanner(context)
    private val audio = AudioFocusHold(context)
    private val memory = LockMemory(context)

    private var lockedManually = false
    private var lockedByBudget = false
    private var lastVerdict: BudgetVerdict? = null

    val isLocked: Boolean get() = overlay.isShowing

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

    fun stop() {
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
        )
        if (!wasShowing) onChanged()
    }

    private fun hide() {
        if (!overlay.isShowing) return
        memory.cause = LockCause.NONE
        overlay.hide()
        // Given back, so the television is exactly as usable as it was. Nothing resumes by
        // itself, which is deliberate — see AudioFocusHold.
        audio.release()
        onChanged()
    }

    private companion object {
        const val SECONDS_PER_MINUTE = 60.0
    }
}
