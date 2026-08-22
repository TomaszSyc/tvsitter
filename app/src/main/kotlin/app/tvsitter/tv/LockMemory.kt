/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.tv

import android.content.Context
import android.util.Log

/** Why the lock was up, if it was. */
enum class LockCause { NONE, BUDGET, MANUAL }

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
        val NONE_NAME: String = LockCause.NONE.name
    }
}
