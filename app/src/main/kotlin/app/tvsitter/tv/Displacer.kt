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

/**
 * Sends the television to its own home screen.
 *
 * The only thing that silences a source audio focus cannot reach. An HDMI input is an ordinary
 * activity here (D12), so bringing the launcher forward puts it in the background — and that
 * does stop the sound. Confirmed by ear, because `dumpsys audio` goes on reporting the input
 * service's track as started either way and is no use as evidence.
 *
 * Its own class because two unrelated things need it: the lock, keeping a console quiet behind a
 * covered screen, and an app that has spent its own budget while the rest of the television is
 * still allowed. The second one has no overlay to hide behind, so the guard about whether the
 * lock is up belongs to the caller rather than in here.
 *
 * Rate-limited rather than once per lock. Once per lock meant a single press of the source key
 * defeated it for good; a cooldown means the television always gets the last word without two
 * processes taking turns.
 */
class Displacer(
    private val context: Context,
    /** Called after each successful trip home, deferred ones included. */
    private val onSentHome: () -> Unit = {},
    /**
     * Called once when the trips home stop looking like accidents.
     *
     * The source key never reaches this app, so a switch can only be undone, never refused —
     * and a child who keeps pressing it gets a second of sound each time. Home Assistant has
     * authority this side does not, so the signal goes there and the answer is the
     * household's: switch the source, cut the power, or do nothing (#59).
     */
    private val onFight: () -> Unit = {},
) {
    private val handler = Handler(Looper.getMainLooper())
    private val again = Runnable { sendHome() }
    private var lastAtMs = 0L
    private var recentTrips = mutableListOf<Long>()
    private var lastFightAtMs = 0L

    /** Resolved once. Sending the home screen home would be a fight with nobody. */
    val homePackage: String? by lazy {
        val home = Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_HOME)
        context.packageManager
            .resolveActivity(home, PackageManager.MATCH_DEFAULT_ONLY)
            ?.activityInfo
            ?.packageName
    }

    fun sendHome() {
        val nowMs = System.currentTimeMillis()
        val since = nowMs - lastAtMs
        if (since < COOLDOWN_MS) {
            // Deferred rather than dropped. Dropping it lost: pressing the source key twice
            // inside the cooldown left the console in front, because the second request went
            // in the bin and nothing else was ever going to arrive. Measured, and it worked.
            handler.removeCallbacks(again)
            handler.postDelayed(again, COOLDOWN_MS - since)
            return
        }
        lastAtMs = nowMs

        val home = Intent(Intent.ACTION_MAIN)
            .addCategory(Intent.CATEGORY_HOME)
            .setFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        val started = runCatching { context.startActivity(home) }
        if (started.isFailure) {
            // Starting an activity from the background is restricted, and the app-op behind the
            // lock window is what exempts us. If that were ever revoked, this is where it would
            // show up rather than as sound that quietly never stops.
            Log.e(EnforcerService.TAG, "audio: could not reach the home screen", started.exceptionOrNull())
            return
        }
        Log.i(EnforcerService.TAG, "audio: sent the TV home to stop what focus could not")
        onSentHome()
        noticeAFight(nowMs)
    }

    fun stop() {
        handler.removeCallbacks(again)
    }

    /**
     * Decides whether this is somebody fighting the lock rather than brushing a key.
     *
     * Once per outbreak, not once per press: an alarm that arrives four times in a minute is
     * one a parent stops reading, which is the mistake #58 was about in a different costume.
     */
    private fun noticeAFight(nowMs: Long) {
        recentTrips = recentTrips.filterTo(mutableListOf()) { nowMs - it < FIGHT_WINDOW_MS }
        recentTrips += nowMs
        if (recentTrips.size < FIGHT_TRIPS) return
        if (nowMs - lastFightAtMs < FIGHT_QUIET_MS) return
        lastFightAtMs = nowMs
        Log.w(EnforcerService.TAG, "lock: ${recentTrips.size} trips home, somebody is at it")
        onFight()
    }

    private companion object {
        /**
         * Long enough that a stubborn app cannot turn this into a tight loop, short enough that
         * pressing the source key buys a couple of seconds of console and no more.
         */
        const val COOLDOWN_MS = 2_000L

        /**
         * Four trips within three minutes. One press of the source key is a mistake, and two
         * is a child finding out what the button does; four is a decision.
         */
        const val FIGHT_TRIPS = 4
        const val FIGHT_WINDOW_MS = 3 * 60 * 1000L

        /** And no more than one alarm every ten minutes, however long they keep at it. */
        const val FIGHT_QUIET_MS = 10 * 60 * 1000L
    }
}
