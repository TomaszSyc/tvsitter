/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.rules.contract

import app.tvsitter.rules.BudgetState
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/** How the day's questions went. Four numbers because four things can become of a request. */
@Serializable
data class RequestTally(val asked: Int = 0, val granted: Int = 0, val denied: Int = 0, val expired: Int = 0)

/**
 * What the television counted during a budget day that cannot be worked out from the counter.
 *
 * Kept on the device across the day and reset with everything else at 04:00. A request that was
 * refused leaves nothing in the budget, and neither does a lock that went up and came down, so
 * without these the day's summary would only be able to say how long the television was on.
 */
@Serializable
data class DayCounters(
    val requests: RequestTally = RequestTally(),
    /** Seconds a parent actually handed over, which is not the same as the bonus still unspent. */
    @SerialName("granted_s") val grantedSeconds: Int = 0,
    /** How many times the screen was covered, for any reason. */
    @SerialName("lock_count") val lockCount: Int = 0,
)

/**
 * One budget day, closed.
 *
 * Published retained when the day rolls over, and nothing older is kept: the archive belongs to
 * whoever is listening — the recorder today, an add-on or a server later (D25) — and a television
 * that keeps a month of history is a television with a database on it.
 *
 * [day] is the budget day as the counter names it, so one in the morning on Saturday is still
 * Friday. That is the same convention everywhere else here, and the reason this is not simply a
 * calendar date.
 */
@Serializable
data class DaySummary(
    val schema: Int = Contract.SCHEMA_VERSION,
    val day: String,
    @SerialName("used_s") val usedSeconds: Int,
    @SerialName("limit_s") val limitSeconds: Int? = null,
    @SerialName("bonus_s") val bonusSeconds: Int = 0,
    @SerialName("per_app") val perApp: Map<String, Int> = emptyMap(),
    @SerialName("per_app_names") val perAppNames: Map<String, String> = emptyMap(),
    val requests: RequestTally = RequestTally(),
    @SerialName("granted_s") val grantedSeconds: Int = 0,
    @SerialName("lock_count") val lockCount: Int = 0,
    val ts: Long,
) {
    companion object {
        /**
         * Describes the day that is ending, from the state that is about to be thrown away.
         *
         * Pure, and given the closing state rather than reading it, because the one thing that
         * must not happen here is the summary being built from the fresh day — which is what
         * makes the rollover the only place it can be called from.
         *
         * [limitSeconds] is what was being enforced, null when nothing was. Not what the rules
         * said: a limit set aside at nine is a day with no limit, and a summary claiming one
         * would make the used total look like an overrun that nobody allowed.
         */
        fun of(
            closing: BudgetState,
            limitSeconds: Long?,
            names: Map<String, String>,
            counters: DayCounters,
            nowMs: Long,
        ): DaySummary = DaySummary(
            day = closing.day.toString(),
            usedSeconds = closing.usedSeconds.toInt(),
            limitSeconds = limitSeconds?.toInt(),
            bonusSeconds = closing.bonusSeconds.toInt(),
            perApp = closing.perAppSeconds.mapValues { it.value.toInt() },
            // Only the packages with time against them, and only their names: the same rule the
            // state payload follows, for the same reason.
            perAppNames = names.filterKeys { it in closing.perAppMillis },
            requests = counters.requests,
            grantedSeconds = counters.grantedSeconds,
            lockCount = counters.lockCount,
            ts = nowMs,
        )
    }
}
