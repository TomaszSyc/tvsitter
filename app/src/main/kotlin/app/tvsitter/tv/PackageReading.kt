/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.tv

import android.util.Log

/**
 * A set of packages asked of the package manager on every read, for answers that can change
 * while the process lives — a launcher or a screen saver installed or disabled over adb (D40).
 *
 * A failed query returns the last answer rather than an empty one. Empty is not a safe default
 * here: no home screen means the allow-list sends the launcher home every ten seconds, and no
 * screen saver means a dark room is charged as viewing.
 *
 * Logged only when the answer changes, because it is read every few seconds — but logged then,
 * including the first time and including an empty answer, since an empty set is silent and wrong
 * and the only way to notice is to read this line.
 */
internal class PackageReading(private val what: String, private val query: () -> Set<String>) {

    // Read from the main thread and from whoever builds the state payload.
    @Volatile private var last: Set<String>? = null

    @Volatile private var failing = false

    fun read(): Set<String> {
        val found = runCatching(query).getOrElse {
            if (!failing) Log.w(EnforcerService.TAG, "could not list $what; keeping ${last.orEmpty().sorted()}", it)
            failing = true
            return last.orEmpty()
        }
        failing = false
        if (found != last) {
            Log.i(EnforcerService.TAG, "$what: ${found.sorted()}")
            last = found
        }
        return found
    }
}
