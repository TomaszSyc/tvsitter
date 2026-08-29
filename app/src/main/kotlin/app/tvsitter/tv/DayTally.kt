/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.tv

import android.content.Context
import android.util.Log
import app.tvsitter.rules.BudgetState
import app.tvsitter.rules.contract.ContractCodec
import app.tvsitter.rules.contract.DayCounters
import app.tvsitter.rules.contract.DaySummary
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.launch

/**
 * What the day looked like beyond how long the television was on.
 *
 * A request that was refused leaves nothing in the counter, and neither does a lock that went up
 * and came down again. Those are exactly the things a parent asks about after the fact — "did he
 * ask?", "how often did it lock?" — so they are counted as they happen and reset with the budget
 * day.
 *
 * Persisted on every change rather than periodically: they change a handful of times a day, and
 * the alternative is losing the evening's answer to a process death at bedtime.
 */
class DayTally(private val context: Context, private val scope: CoroutineScope) {

    @Volatile
    private var counters = DayCounters()

    suspend fun load() {
        counters = Settings(context).dayCounters()
    }

    fun recordAsked() = change { it.copy(requests = it.requests.copy(asked = it.requests.asked + 1)) }

    fun recordDenied() = change { it.copy(requests = it.requests.copy(denied = it.requests.denied + 1)) }

    fun recordExpired() = change { it.copy(requests = it.requests.copy(expired = it.requests.expired + 1)) }

    fun recordGranted(seconds: Long) = change {
        it.copy(
            requests = it.requests.copy(granted = it.requests.granted + 1),
            grantedSeconds = it.grantedSeconds + seconds.toInt(),
        )
    }

    fun recordLock() = change { it.copy(lockCount = it.lockCount + 1) }

    /**
     * Describes the day that is ending and starts the next one at zero.
     *
     * Given the closing state rather than reading the counter, because by the time this is
     * called the counter is already on the new day — which is the one mistake that would make
     * every summary describe an empty morning.
     */
    fun close(closing: BudgetState, limitSeconds: Long?, names: Map<String, String>): DaySummary {
        val summary = DaySummary.of(closing, limitSeconds, names, counters, System.currentTimeMillis())
        counters = DayCounters()
        val payload = ContractCodec.encode(summary)
        scope.launch {
            runCatching {
                Settings(context).saveDayCounters(DayCounters())
                Settings(context).saveLastDay(payload)
            }.onFailure { Log.w(EnforcerService.TAG, "day: could not persist the summary", it) }
        }
        Log.i(EnforcerService.TAG, "day closed: $payload")
        return summary
    }

    private fun change(transform: (DayCounters) -> DayCounters) {
        counters = transform(counters)
        val snapshot = counters
        scope.launch {
            runCatching { Settings(context).saveDayCounters(snapshot) }
                .onFailure { Log.w(EnforcerService.TAG, "day: could not persist counters", it) }
        }
    }
}
