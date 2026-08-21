/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.tv

import android.app.usage.UsageEvents
import android.app.usage.UsageStatsManager
import android.content.Context
import android.util.Log

/**
 * Which app is in the foreground, from `UsageStatsManager`.
 *
 * Replaces the accessibility service's window events (D16). Polled rather than pushed, which
 * is the price of not needing an accessibility service enabled — and per D15 that price is
 * worth paying, because merely having one enabled unmasks password fields system-wide.
 *
 * A poll asks for events since the last one and takes the most recent resume. Reading events
 * rather than aggregate stats matters: aggregates tell you what was used today, events tell
 * you what came to the front and when.
 */
class ForegroundAppMonitor(context: Context, private val onChanged: (String) -> Unit) {
    private val usageStatsManager = context.getSystemService(UsageStatsManager::class.java)
    private var lastQueriedAt = System.currentTimeMillis() - INITIAL_LOOKBACK_MS

    @Volatile
    var current: String? = null
        private set

    /** True when the permission is missing, which is the usual reason for seeing nothing. */
    val isUsable: Boolean get() = usageStatsManager != null

    fun poll() {
        val manager = usageStatsManager ?: return
        val now = System.currentTimeMillis()

        // A small overlap on purpose: query boundaries are not exact, and missing the one
        // event that matters is worse than processing it twice.
        val events = runCatching {
            manager.queryEvents(lastQueriedAt - QUERY_OVERLAP_MS, now)
        }.getOrElse {
            Log.w(EnforcerService.TAG, "usage events unavailable", it)
            return
        }
        lastQueriedAt = now

        var latest: String? = null
        val event = UsageEvents.Event()
        while (events.hasNextEvent()) {
            events.getNextEvent(event)
            // ACTIVITY_RESUMED is the modern name and MOVE_TO_FOREGROUND the old one; they
            // are the same value, and the old one exists across the whole supported range.
            @Suppress("DEPRECATION")
            if (event.eventType == UsageEvents.Event.MOVE_TO_FOREGROUND) {
                latest = event.packageName
            }
        }

        val resolved = latest ?: return
        if (resolved == current) return
        current = resolved
        Log.i(EnforcerService.TAG, "foreground=$resolved")
        onChanged(resolved)
    }

    private companion object {
        const val INITIAL_LOOKBACK_MS = 60_000L
        const val QUERY_OVERLAP_MS = 2_000L
    }
}
