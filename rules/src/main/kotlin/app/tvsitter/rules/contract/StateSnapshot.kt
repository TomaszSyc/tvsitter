/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.rules.contract

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/**
 * What the TV publishes on `<prefix>/state`, retained.
 *
 * `remainingTodaySeconds` is null for "no limit", which is a different thing from zero;
 * anything reading it has to keep that distinction or an unlimited evening turns into an
 * instant lock.
 */
@Serializable
data class StateSnapshot(
    val schema: Int = Contract.SCHEMA_VERSION,
    /** Send time, epoch milliseconds. Lets a consumer recognise a stale retained payload. */
    val ts: Long,
    /** App version, so a misbehaving build can be identified from the payload alone. */
    val fw: String,
    @SerialName("screen_on") val screenOn: Boolean,
    val locked: Boolean,
    @SerialName("app_id") val appId: String? = null,
    @SerialName("app_name") val appName: String? = null,
    @SerialName("used_today_s") val usedTodaySeconds: Int = 0,
    /** The limit in force, or null when none is. Not the same question as what is left. */
    @SerialName("limit_today_s") val limitTodaySeconds: Int? = null,
    @SerialName("remaining_today_s") val remainingTodaySeconds: Int? = null,
    @SerialName("bonus_today_s") val bonusTodaySeconds: Int = 0,
    @SerialName("per_app") val perApp: Map<String, Int> = emptyMap(),
    /** Identifier of the rule window in force, so "why did it block me now" is answerable. */
    @SerialName("active_window") val activeWindow: String? = null,
    /** Why the screen is covered, or null when it is not. `manual` for a parent's own lock. */
    @SerialName("lock_reason") val lockReason: String? = null,
    /**
     * How long viewing may still go on, counting whichever rule binds first.
     *
     * Not the same as [remainingTodaySeconds], which is the day's budget and nothing else. A
     * window closing at half past seven is what stops the evening even with an hour of budget
     * left, and that is the number the television is counting down to.
     */
    @SerialName("until_s") val untilSeconds: Int? = null,
    @SerialName("rules_rev") val rulesRev: Int = 0,
    /**
     * Whether a parent PIN exists. Not the PIN, and not its hash: nothing that could be
     * attacked offline leaves the television. What this answers is whether the lock can be
     * lifted at the set itself, which is worth knowing before the evening Home Assistant is
     * unreachable rather than during it.
     */
    @SerialName("pin_set") val pinSet: Boolean = false,
    /** When the PIN last changed, epoch milliseconds, or null if it never has. */
    @SerialName("pin_changed_at") val pinChangedAt: Long? = null,
    /**
     * Where that change was made, `tv` or `ha`.
     *
     * The timestamp alone says something happened; this says whether it could have been you.
     * A PIN changed from Home Assistant was changed by somebody holding the parent's phone or
     * laptop — a PIN changed on the television was changed by whoever was in the room.
     */
    @SerialName("pin_changed_by") val pinChangedBy: String? = null,
)

/**
 * What the TV publishes on `<prefix>/request` when a child asks for more time. Not retained:
 * a retained request would be answered again after every broker restart.
 */
@Serializable
data class TimeRequest(
    val schema: Int = Contract.SCHEMA_VERSION,
    /** Stable for one request. The app ignores a grant carrying an unknown or settled id. */
    val id: String,
    val kind: String = KIND_MORE_TIME,
    @SerialName("app_id") val appId: String? = null,
    /**
     * What the app is called, as the television resolves it.
     *
     * Sent rather than left to the other side to work out. Home Assistant can only pair the
     * package name against whatever the last state payload said, and a child who changes app
     * in the same breath as asking breaks that — leaving a parent reading a package name off
     * their phone.
     */
    @SerialName("app_name") val appName: String? = null,
    @SerialName("asked_minutes") val askedMinutes: Int,
    val ts: Long,
) {
    companion object {
        const val KIND_MORE_TIME: String = "more_time"
    }
}
