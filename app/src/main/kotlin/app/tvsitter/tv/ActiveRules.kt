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

    val dailyLimitSeconds: Long? get() = rules.dailyLimitSeconds

    suspend fun load() {
        val stored = Settings(context).rules()
        rules = stored.rules
        revision = stored.revision
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
        val parsed = Rules.fromJson(json)
        Settings(context).saveRules(json.toString(), rev)
        rules = parsed
        revision = rev
        Log.i(
            EnforcerService.TAG,
            "rules: applied rev=$rev limit=${parsed.dailyLimitSeconds ?: "none"}",
        )
    }
}
