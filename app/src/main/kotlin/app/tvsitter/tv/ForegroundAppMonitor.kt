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
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch

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

    /**
     * Runs the polling loop until [scope] is cancelled. Owned here rather than in the service:
     * the interval belongs with the thing being polled.
     *
     * [isScreenOn] is consulted rather than captured, so nothing is queried while the panel is
     * off — there is no foreground app worth counting then.
     */
    fun start(scope: CoroutineScope, isScreenOn: () -> Boolean) {
        if (!isUsable) {
            Log.e(EnforcerService.TAG, "usage stats unavailable — nothing will be detected")
            return
        }
        scope.launch {
            while (scope.isActive) {
                if (isScreenOn()) poll()
                delay(POLL_INTERVAL_MS)
            }
        }
    }

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

        val resolved = latest ?: seedFromHistory(manager, now) ?: return
        if (resolved == current) return
        current = resolved
        Log.i(EnforcerService.TAG, "foreground=$resolved")
        onChanged(resolved)
    }

    /**
     * What was already in front before anyone started looking.
     *
     * Events only say what *moved*, so an app that came forward before the service started
     * produces none — and something has usually been playing for half an hour by then. The
     * monitor then knew nothing at all until the next time somebody changed app, which meant
     * the lock had nothing to displace and went up over a programme that carried on playing
     * with the sound on (#92). Measured: Netflix in front, `foreground=null`, no displacement.
     *
     * Asked only while nothing is known, and answered from the daily summary rather than the
     * event stream: the most recently used package is the one in front. Once an event has
     * arrived this is never consulted again, because events are the better answer.
     */
    private fun seedFromHistory(manager: UsageStatsManager, now: Long): String? {
        if (current != null) return null
        val used = runCatching {
            manager.queryUsageStats(UsageStatsManager.INTERVAL_DAILY, now - SEED_LOOKBACK_MS, now)
        }.getOrElse {
            Log.w(EnforcerService.TAG, "usage summary unavailable", it)
            return null
        }
        val front = used.maxByOrNull { it.lastTimeUsed }?.packageName ?: return null
        Log.i(EnforcerService.TAG, "foreground seeded from history: $front")
        return front
    }

    private companion object {
        const val POLL_INTERVAL_MS = 1_500L
        const val INITIAL_LOOKBACK_MS = 60_000L
        const val QUERY_OVERLAP_MS = 2_000L

        /** A day. Long enough that something is always in it, short enough to stay one query. */
        const val SEED_LOOKBACK_MS = 24 * 60 * 60 * 1000L
    }
}
