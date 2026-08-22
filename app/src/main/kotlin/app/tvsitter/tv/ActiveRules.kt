/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.tv

import android.content.Context
import android.util.Log
import app.tvsitter.rules.Rules
import kotlinx.serialization.json.JsonObject

/**
 * The rules this TV is enforcing, and where they are kept.
 *
 * Kept on the device rather than fetched, per D3: a Home Assistant outage, a dropped link or
 * a broker restart must not lift a limit. Home Assistant is where rules are edited, not where
 * they live.
 *
 * The stored form is the raw JSON from `set_rules` rather than parsed fields, so adding a rule
 * later needs no storage migration — the contract keeps `rules` opaque for the same reason.
 */
class ActiveRules(private val context: Context) {

    @Volatile
    var rules: Rules = Rules.NONE
        private set

    @Volatile
    var revision: Int = 0
        private set

    /** The rules exactly as stored, so an incoming change can be folded into them. */
    private var stored: JsonObject = JsonObject(emptyMap())

    val dailyLimitSeconds: Long? get() = rules.dailyLimitSeconds

    suspend fun load() {
        val loaded = Settings(context).rules()
        stored = loaded.json
        rules = loaded.rules
        revision = loaded.revision
        Log.i(
            EnforcerService.TAG,
            "rules: loaded rev=$revision limit=${rules.dailyLimitSeconds ?: "none"}",
        )
    }

    /**
     * Applies rules that arrived over MQTT and writes them down before acknowledging them.
     *
     * Persisted first: the revision is echoed in the state payload so Home Assistant can see
     * the two sides agree, and echoing a revision that would not survive a restart would be
     * a claim we cannot keep.
     */
    suspend fun apply(json: JsonObject, rev: Int) {
        // The contract's rule, and not a theoretical one: `cmd` is QoS 1, which is
        // at-least-once, so the same message can arrive twice and two messages can arrive out
        // of order. Without this, a redelivered older `set_rules` silently rolls the limit
        // back to what it was, and nothing anywhere says it happened.
        if (rev <= revision) {
            Log.i(EnforcerService.TAG, "rules: ignoring rev=$rev, already at rev=$revision")
            return
        }

        // Merged, not replaced. Whoever sent this knows about the rules it is changing and
        // need not know about the rest, so a control for the limit cannot wipe a schedule it
        // has never heard of. A key carrying null removes it.
        val merged = Rules.merge(stored, json)
        val parsed = Rules.fromJson(merged)

        Settings(context).saveRules(merged.toString(), rev)
        stored = merged
        rules = parsed
        revision = rev
        Log.i(
            EnforcerService.TAG,
            "rules: applied rev=$rev limit=${parsed.dailyLimitSeconds ?: "none"} " +
                "keys=${merged.keys.sorted()}",
        )
    }
}
