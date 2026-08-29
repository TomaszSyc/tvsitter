/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.tv

import android.os.SystemClock
import android.util.Log
import app.tvsitter.rules.ClockWatch

/**
 * What the time is, after taking off however far somebody has moved it.
 *
 * The budget day is wall-clock throughout, and date and time are a few D-pad presses away for as
 * long as Settings is reachable — so a spent day could be turned into a fresh one, and the
 * counter would not even notice: it measures differences between readings of the same clock, and
 * a clock that jumps takes the differences with it.
 *
 * `elapsedRealtime` is the second opinion. It counts since boot, keeps counting in sleep, and
 * nobody can set it, so the two deltas between a pair of readings should agree. When they do
 * not, the difference is the jump, and it is subtracted from everything downstream: the day
 * stands and the anchor moves by the time that actually passed.
 *
 * Both clocks are read here and nowhere else, so there is one place where a jump can be noticed
 * and one definition of "now" for everything that depends on it.
 *
 * The offset is in memory and not on disk, deliberately: `elapsedRealtime` restarts with the
 * device, so after a reboot there is no second opinion left and the wall clock has to be believed
 * again. That leaves rebooting as the way round this, which is worth writing down rather than
 * pretending otherwise.
 */
class TrustedClock(private val onJump: (Long) -> Unit = {}) {

    @Volatile
    private var offsetMs = 0L
    private var lastWallMs = 0L
    private var lastElapsedMs = 0L

    fun now(): Long {
        val wallMs = System.currentTimeMillis()
        val elapsedMs = SystemClock.elapsedRealtime()
        if (lastWallMs != 0L) {
            val jump = ClockWatch.jumpBetween(wallMs - lastWallMs, elapsedMs - lastElapsedMs)
            if (jump != 0L) {
                offsetMs += jump
                Log.w(
                    EnforcerService.TAG,
                    "clock: moved by ${jump / MILLIS_PER_SECOND}s, ignoring it for the budget",
                )
                onJump(jump)
            }
        }
        lastWallMs = wallMs
        lastElapsedMs = elapsedMs
        return ClockWatch.trusted(wallMs, offsetMs)
    }

    private companion object {
        const val MILLIS_PER_SECOND = 1_000L
    }
}
