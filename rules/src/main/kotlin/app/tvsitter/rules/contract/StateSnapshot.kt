/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.rules.contract

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonObject

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
    /**
     * Friendly names for the packages in [perApp], and only those.
     *
     * The labels live on the television and nowhere else, so without this a graph of what a
     * child watches is a graph of `com.google.android.youtube.tv`. Sent beside the numbers
     * rather than resolved on the other side, because only the set that has them can.
     */
    @SerialName("per_app_names") val perAppNames: Map<String, String> = emptyMap(),
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
     * Packages the rules cannot touch, so nothing offers a control for them.
     *
     * The engine exempts this app and the launcher from an allow-list on purpose (D35) — the
     * answer to "the launcher is not allowed" would be to send the television to the launcher,
     * every ten seconds, for as long as it was on. A tick beside one of these does nothing,
     * and a control that does nothing is worse than none.
     *
     * Published because only the television knows them: they are resolved from the platform,
     * and Home Assistant has no way to ask (#130). Empty from a set that has not been updated,
     * which reads as "nothing known to be exempt" rather than as a promise.
     */
    @SerialName("exempt_apps") val exemptApps: List<String> = emptyList(),
    /**
     * Whether the television can still draw over other apps, and still read usage.
     *
     * Either being false means the product is not working, and both are one Settings screen
     * away. Published rather than only alarmed about, so a dashboard can say so plainly and a
     * parent who missed the alarm still finds out.
     */
    @SerialName("can_overlay") val canOverlay: Boolean = true,
    @SerialName("can_usage") val canUsage: Boolean = true,
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

/**
 * Something happened that a parent should hear about, and that no state field can carry.
 *
 * Retained state is the wrong shape for these: a counter in it rewrites the payload on every
 * wrong keypress, and a value cannot say *when*. A request is the right shape and the wrong
 * subject. So this is its own topic, and every tamper signal is a [kind] on it.
 *
 * [id] is stable for one occurrence, so a redelivered alert is not a second alarm — the same
 * reason a time request carries one. [detail] is free per kind, because "five wrong guesses,
 * locked until 21:14" and "the clock moved four hours" have nothing in common but their shape.
 */
@Serializable
data class Alert(
    val schema: Int = Contract.SCHEMA_VERSION,
    val id: String,
    val kind: String,
    val ts: Long,
    val detail: JsonObject = JsonObject(emptyMap()),
)

/**
 * The kinds, registered as they are built.
 *
 * Strings rather than an enum because Home Assistant has to understand one it has never seen —
 * a newer television must be able to raise an alarm an older integration can still show, rather
 * than one it refuses to decode.
 */
object AlertKind {
    /** The keypad shut after too many wrong guesses. */
    const val PIN_LOCKOUT: String = "pin_lockout"

    /** The television's clock moved by more than sleep and drift explain. */
    const val CLOCK_CHANGED: String = "clock_changed"

    /** Permission to draw over other apps is gone, so the lock cannot appear. */
    const val OVERLAY_LOST: String = "overlay_lost"

    /** Usage access is gone, so nothing can be counted or displaced. */
    const val USAGE_LOST: String = "usage_lost"

    /** The service came back without having been asked to stop. */
    const val UNCLEAN_RESTART: String = "unclean_restart"

    /** Something keeps coming back in front of the lock. */
    const val SOURCE_FIGHT: String = "source_fight"
}
