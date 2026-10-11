/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.tv

import android.content.Context
import android.os.SystemClock
import android.provider.Settings
import android.util.Log
import app.tvsitter.rules.TrustedTime

/**
 * What the time is, after taking off however far somebody has moved it by hand.
 *
 * The budget day is wall-clock throughout, and date and time are a few D-pad presses away for as
 * long as Settings is reachable — so a spent day could be turned into a fresh one. `elapsedRealtime`
 * is the second opinion: it counts since boot and nobody can set it. The deciding is in
 * [TrustedTime]; this class reads the two clocks, and whether the system is setting the time from
 * the network, which is what tells a correction from tampering (see there).
 *
 * Both clocks are read here and nowhere else, so there is one definition of "now" for everything
 * that depends on it. The offset is in memory, so a reboot drops it; with network time on there is
 * none to drop.
 *
 * The context is only read inside [now], so a service can build this in a field initializer.
 */
class TrustedClock(private val context: Context, onJump: (Long) -> Unit = {}) {

    private val time = TrustedTime { jump ->
        Log.w(EnforcerService.TAG, "clock: moved by ${jump / MILLIS_PER_SECOND}s, ignoring it for the budget")
        onJump(jump)
    }

    fun now(): Long = time.now(System.currentTimeMillis(), SystemClock.elapsedRealtime(), networkTime())

    private fun networkTime(): Boolean =
        Settings.Global.getInt(context.contentResolver, Settings.Global.AUTO_TIME, 1) == 1

    private companion object {
        const val MILLIS_PER_SECOND = 1_000L
    }
}
