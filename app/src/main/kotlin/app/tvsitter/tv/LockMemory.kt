/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.tv

import android.content.Context
import android.util.Log
import app.tvsitter.rules.LockCause

/**
 * The one thing this app remembers in device-encrypted storage.
 *
 * A manual lock has no other record of itself. The budget lock can be worked out again from
 * the counter and the rules, so it survives a restart on its own; a lock a parent put up is
 * a decision, not a calculation, and without this a reboot forgot it. That is what this file
 * is for, and why it stores the cause rather than a flag: restored as a budget lock it lifts
 * as soon as there is time, and restored as a manual one it stays.
 *
 * Device-encrypted rather than alongside everything else, because a boot receiver may run
 * before credential-encrypted storage exists (D22). On this television it does not — the user
 * is already unlocked by then — but a device with a real credential lock would.
 *
 * SharedPreferences rather than DataStore: it is synchronous, which is what a boot receiver
 * with nothing else to wait for actually wants, and it is one value.
 */
class LockMemory(context: Context) {

    private val preferences = context
        .createDeviceProtectedStorageContext()
        .getSharedPreferences(FILE, Context.MODE_PRIVATE)

    /**
     * Until when a manual lock is standing down, epoch milliseconds. Zero when it is not.
     *
     * Kept here rather than in memory because it is the deadline a child would most like to
     * lose: a parent granted fifteen minutes, and pulling the plug must not turn that into
     * the rest of the evening.
     */
    var pausedUntilMs: Long
        get() = preferences.getLong(KEY_PAUSED_UNTIL, 0)
        set(value) {
            preferences.edit().putLong(KEY_PAUSED_UNTIL, value).apply()
        }

    /**
     * When the television has to lock itself tonight, epoch milliseconds. Zero for never.
     *
     * Device-encrypted with the rest of this for the same reason: a deadline a child would
     * most like to lose is one they can lose by pulling the plug.
     */
    var sleepAtMs: Long
        get() = preferences.getLong(KEY_SLEEP_AT, 0)
        set(value) {
            preferences.edit().putLong(KEY_SLEEP_AT, value).apply()
        }

    /**
     * Whether the last run ended by being asked to.
     *
     * False at start means the previous one was force-stopped, killed for memory, or died —
     * and nothing else in the package would ever mention it. START_STICKY does not cover a
     * force-stop, and Android offers no way to prevent one without Device Owner, so the honest
     * scope is evidence rather than prevention.
     */
    var cleanShutdown: Boolean
        get() = preferences.getBoolean(KEY_CLEAN, true)
        set(value) {
            preferences.edit().putBoolean(KEY_CLEAN, value).apply()
        }

    var cause: LockCause
        get() = runCatching { LockCause.valueOf(preferences.getString(KEY, null) ?: NONE_NAME) }
            .getOrElse {
                // An unreadable value means starting unlocked, which is the safe direction:
                // a lock that fails to come back is a complaint, a TV stuck behind a lock
                // nobody can explain is worse.
                Log.w(EnforcerService.TAG, "lock memory unreadable, assuming unlocked", it)
                LockCause.NONE
            }
        set(value) {
            preferences.edit().putString(KEY, value.name).apply()
        }

    private companion object {
        const val FILE = "lock_memory"
        const val KEY = "cause"
        const val KEY_PAUSED_UNTIL = "paused_until"
        const val KEY_SLEEP_AT = "sleep_at"
        const val KEY_CLEAN = "clean_shutdown"
        val NONE_NAME: String = LockCause.NONE.name
    }
}
