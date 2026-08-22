/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.tv

import android.content.Context
import android.util.Log
import app.tvsitter.rules.PinHash
import app.tvsitter.rules.PinLockout
import kotlinx.serialization.json.Json

/**
 * Where the parent PIN lives on the device: the hash, the counter of wrong guesses, and a note
 * of when it last changed.
 *
 * Device-encrypted storage, alongside [LockMemory] rather than with everything else. The lock
 * can be back up before the user has unlocked the device (D22), and a keypad that cannot read
 * the hash at that point would have to tell a parent standing in front of a locked television
 * to unlock the television first. For a hash this costs nothing: device-encrypted storage is
 * no more readable by another app than credential-encrypted storage is, and both are readable
 * by anyone with root — which is the reason the PIN is hashed rather than stored.
 *
 * The three parts of the hash are written as one value so a torn write cannot leave a salt
 * belonging to a different PIN than the digest.
 */
class PinStore(context: Context) {

    private val preferences = context
        .createDeviceProtectedStorageContext()
        .getSharedPreferences(FILE, Context.MODE_PRIVATE)

    /** Null when this television has no PIN, which is different from an empty one. */
    var hash: PinHash?
        get() = preferences.getString(KEY_HASH, null)?.let { stored ->
            runCatching { Json.decodeFromString<PinHash>(stored) }.getOrElse {
                // Treated as no PIN rather than as a locked television. A parent who cannot
                // type their way in has Home Assistant; a household locked out by a corrupt
                // file has nothing.
                Log.w(EnforcerService.TAG, "pin: stored hash unreadable, treating as unset", it)
                null
            }
        }
        set(value) {
            preferences.edit().apply {
                if (value == null) remove(KEY_HASH) else putString(KEY_HASH, Json.encodeToString(value))
            }.apply()
        }

    var lockout: PinLockout
        get() = PinLockout(
            failures = preferences.getInt(KEY_FAILURES, 0),
            lockedUntilMs = preferences.getLong(KEY_LOCKED_UNTIL, 0),
            lockouts = preferences.getInt(KEY_LOCKOUTS, 0),
        )
        set(value) {
            preferences.edit()
                .putInt(KEY_FAILURES, value.failures)
                .putLong(KEY_LOCKED_UNTIL, value.lockedUntilMs)
                // Kept with the rest, or force-stopping the app would put the wait back to
                // five minutes — which is the whole point of it growing.
                .putInt(KEY_LOCKOUTS, value.lockouts)
                .apply()
        }

    /** Zero when the PIN has never been changed. */
    var changedAtMs: Long
        get() = preferences.getLong(KEY_CHANGED_AT, 0)
        set(value) {
            preferences.edit().putLong(KEY_CHANGED_AT, value).apply()
        }

    /** `tv` or `ha`, as [app.tvsitter.rules.contract.Contract] defines them. */
    var changedBy: String?
        get() = preferences.getString(KEY_CHANGED_BY, null)
        set(value) {
            preferences.edit().apply {
                if (value == null) remove(KEY_CHANGED_BY) else putString(KEY_CHANGED_BY, value)
            }.apply()
        }

    private companion object {
        const val FILE = "parent_pin"
        const val KEY_HASH = "hash"
        const val KEY_FAILURES = "failures"
        const val KEY_LOCKED_UNTIL = "locked_until"
        const val KEY_LOCKOUTS = "lockouts"
        const val KEY_CHANGED_AT = "changed_at"
        const val KEY_CHANGED_BY = "changed_by"
    }
}
