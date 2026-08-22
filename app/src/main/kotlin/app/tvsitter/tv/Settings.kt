/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.tv

import android.content.Context
import android.util.Log
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.intPreferencesKey
import androidx.datastore.preferences.core.longPreferencesKey
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import app.tvsitter.rules.BudgetState
import app.tvsitter.rules.Rules
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonObject
import java.time.Clock
import java.time.LocalDate

/** Rules and the revision they came with, which travel together or not at all. */
data class StoredRules(val json: JsonObject, val rules: Rules, val revision: Int)

/** Where to reach the broker, and under which prefix to talk. */
data class BrokerConfig(
    val host: String,
    val port: Int,
    val username: String,
    val password: String,
    val topicPrefix: String,
    val useTls: Boolean,
) {
    val isComplete: Boolean get() = host.isNotBlank() && topicPrefix.isNotBlank()
}

private val Context.dataStore: DataStore<Preferences> by preferencesDataStore(name = "tvsitter")

/**
 * Configuration storage.
 *
 * DataStore rather than SharedPreferences because M2 has to persist the screen-time counter
 * on a timer, and one storage mechanism is better than two.
 */
class Settings(private val context: Context) {

    val broker: Flow<BrokerConfig> = context.dataStore.data.map { prefs ->
        BrokerConfig(
            host = prefs[KEY_HOST].orEmpty(),
            port = prefs[KEY_PORT] ?: DEFAULT_PORT,
            username = prefs[KEY_USERNAME].orEmpty(),
            password = prefs[KEY_PASSWORD].orEmpty(),
            topicPrefix = prefs[KEY_TOPIC_PREFIX] ?: DEFAULT_TOPIC_PREFIX,
            useTls = prefs[KEY_USE_TLS] ?: false,
        )
    }

    suspend fun brokerSnapshot(): BrokerConfig = broker.first()

    /**
     * A stable identifier for this installation, generated once and kept.
     *
     * Deliberately not ANDROID_ID: that is a device identifier, and all this needs to be is
     * something that stays the same across restarts so a paired TV keeps its identity. A
     * random value is both narrower and sufficient.
     */
    suspend fun deviceId(): String {
        context.dataStore.data.first()[KEY_DEVICE_ID]?.let { return it }
        val generated = java.util.UUID.randomUUID().toString().take(DEVICE_ID_LENGTH)
        context.dataStore.edit { prefs -> prefs[KEY_DEVICE_ID] = generated }
        return generated
    }

    /** Rules as last written, with the revision they arrived under. */
    suspend fun rules(): StoredRules {
        val prefs = context.dataStore.data.first()
        val raw = prefs[KEY_RULES_JSON]
        val json = raw?.let {
            runCatching { Json.parseToJsonElement(it).jsonObject }.getOrElse { error ->
                // Unreadable rules mean enforcing none, which is the safe direction: a TV that
                // stops limiting is a complaint, a TV that locks on garbage is not.
                Log.w(EnforcerService.TAG, "unreadable rules, enforcing none", error)
                null
            }
        } ?: JsonObject(emptyMap())
        return StoredRules(json, Rules.fromJson(json), prefs[KEY_RULES_REV] ?: 0)
    }

    suspend fun saveRules(json: String, revision: Int) {
        context.dataStore.edit { prefs ->
            prefs[KEY_RULES_JSON] = json
            prefs[KEY_RULES_REV] = revision
        }
    }

    /**
     * The screen-time counter, as last written.
     *
     * [BudgetState.lastSampleAtMs] is persisted with the totals rather than derived at start.
     * Without it a restart cannot tell a long absence from a long session, and the first
     * sample after coming back would either invent time or discard real time.
     */
    suspend fun budget(clock: Clock = Clock.systemDefaultZone()): BudgetState {
        val prefs = context.dataStore.data.first()
        val storedDay = prefs[KEY_BUDGET_DAY]
        return BudgetState(
            day = storedDay?.let { runCatching { LocalDate.parse(it) }.getOrNull() }
                ?: LocalDate.now(clock),
            usedMillis = prefs[KEY_BUDGET_USED_MS] ?: 0,
            bonusMillis = prefs[KEY_BUDGET_BONUS_MS] ?: 0,
            perAppMillis = decodePerApp(prefs[KEY_BUDGET_PER_APP]),
            lastSampleAtMs = prefs[KEY_BUDGET_LAST_SAMPLE_MS],
            limitSuspended = prefs[KEY_BUDGET_LIMIT_SUSPENDED] ?: false,
        )
    }

    suspend fun saveBudget(state: BudgetState) {
        context.dataStore.edit { prefs ->
            prefs[KEY_BUDGET_DAY] = state.day.toString()
            prefs[KEY_BUDGET_USED_MS] = state.usedMillis
            prefs[KEY_BUDGET_BONUS_MS] = state.bonusMillis
            prefs[KEY_BUDGET_PER_APP] = Json.encodeToString(state.perAppMillis)
            state.lastSampleAtMs?.let { prefs[KEY_BUDGET_LAST_SAMPLE_MS] = it }
            prefs[KEY_BUDGET_LIMIT_SUSPENDED] = state.limitSuspended
        }
    }

    private fun decodePerApp(stored: String?): Map<String, Long> {
        if (stored.isNullOrBlank()) return emptyMap()
        // A corrupt breakdown loses the per-app split for the day and nothing else, which is
        // a better outcome than refusing to start.
        return runCatching { Json.decodeFromString<Map<String, Long>>(stored) }.getOrElse {
            Log.w(EnforcerService.TAG, "unreadable per-app breakdown, dropping it", it)
            emptyMap()
        }
    }

    /**
     * Read, modify, write. A partial update is then just `copy()` at the call site, which
     * beats a row of nullable parameters where every one means "leave this alone".
     */
    suspend fun updateBroker(transform: (BrokerConfig) -> BrokerConfig) {
        val updated = transform(brokerSnapshot())
        context.dataStore.edit { prefs ->
            prefs[KEY_HOST] = updated.host
            prefs[KEY_PORT] = updated.port
            prefs[KEY_USERNAME] = updated.username
            prefs[KEY_PASSWORD] = updated.password
            prefs[KEY_TOPIC_PREFIX] = updated.topicPrefix
            prefs[KEY_USE_TLS] = updated.useTls
        }
    }

    private companion object {
        val KEY_HOST = stringPreferencesKey("broker_host")
        val KEY_PORT = intPreferencesKey("broker_port")
        val KEY_USERNAME = stringPreferencesKey("broker_username")
        val KEY_PASSWORD = stringPreferencesKey("broker_password")
        val KEY_TOPIC_PREFIX = stringPreferencesKey("topic_prefix")
        val KEY_USE_TLS = booleanPreferencesKey("broker_tls")

        val KEY_DEVICE_ID = stringPreferencesKey("device_id")

        val KEY_BUDGET_DAY = stringPreferencesKey("budget_day")
        val KEY_BUDGET_USED_MS = longPreferencesKey("budget_used_ms")
        val KEY_BUDGET_BONUS_MS = longPreferencesKey("budget_bonus_ms")
        val KEY_BUDGET_PER_APP = stringPreferencesKey("budget_per_app")
        val KEY_BUDGET_LAST_SAMPLE_MS = longPreferencesKey("budget_last_sample_ms")
        val KEY_BUDGET_LIMIT_SUSPENDED = booleanPreferencesKey("budget_limit_suspended")

        val KEY_RULES_JSON = stringPreferencesKey("rules_json")
        val KEY_RULES_REV = intPreferencesKey("rules_rev")

        const val DEVICE_ID_LENGTH = 8
        const val DEFAULT_PORT = 1883
        const val DEFAULT_TOPIC_PREFIX = "tvsitter/livingroom"
    }
}
