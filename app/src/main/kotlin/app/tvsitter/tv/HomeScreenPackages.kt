/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.tv

import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import app.tvsitter.rules.HomeClaim
import app.tvsitter.rules.HomeScreens

/**
 * Which packages are a home screen, so the lock and the allow-list never send one home.
 *
 * Sending the home screen home is a fight with nobody, and with an allow-list it is worse: the
 * launcher comes forward, is not on the list, and is sent home again every ten seconds.
 *
 * Every launcher answering HOME rather than the one HOME resolves to, and asked on every check
 * rather than once (D40): a second launcher installed over adb, or the stock one disabled, used
 * to stay invisible until the service restarted, which on this set means weeks. Which answers
 * count — fallbacks out — is [HomeScreens], so it can be tested away from a television.
 */
class HomeScreenPackages(context: Context) {

    private val reading = PackageReading("home screens") {
        val home = Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_HOME)
        val claims = context.packageManager
            .queryIntentActivities(home, PackageManager.MATCH_DEFAULT_ONLY)
            .mapNotNull { info -> info.activityInfo?.let { HomeClaim(it.packageName, info.priority) } }
        HomeScreens.of(claims)
    }

    fun contains(packageName: String?): Boolean = packageName != null && packageName in reading.read()

    /** The whole set, for the list of what the lock and the allow-list leave alone. */
    val all: Set<String> get() = reading.read()
}
