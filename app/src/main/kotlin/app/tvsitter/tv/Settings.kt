/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.tv

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.intPreferencesKey
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map

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

        const val DEFAULT_PORT = 1883
        const val DEFAULT_TOPIC_PREFIX = "tvsitter/livingroom"
    }
}
