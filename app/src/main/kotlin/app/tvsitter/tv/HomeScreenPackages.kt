/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.tv

import android.content.Context
import android.content.Intent
import android.content.pm.ApplicationInfo
import android.content.pm.PackageManager
import app.tvsitter.rules.HomeClaim
import app.tvsitter.rules.HomeScreens

/**
 * Which packages are a home screen, so the lock and the allow-list never send one home.
 *
 * Sending the home screen home is a fight with nobody, and with an allow-list it is worse: the
 * launcher comes forward, is not on the list, and is sent home again every ten seconds.
 *
 * The launchers that came with the firmware plus the one HOME is set to, asked on every check
 * rather than once (D40): a launcher installed over adb and chosen as home, or the stock one
 * disabled, used to stay invisible until the service restarted, which on this set means weeks.
 * Which answers count — fallbacks out, unchosen installed launchers out — is [HomeScreens], so it
 * can be tested away from a television.
 */
class HomeScreenPackages(context: Context) {

    private val reading = PackageReading("home screens") {
        val pm = context.packageManager
        val home = Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_HOME)
        val claims = pm.queryIntentActivities(home, PackageManager.MATCH_DEFAULT_ONLY).mapNotNull { info ->
            info.activityInfo?.let {
                val system = it.applicationInfo.flags and ApplicationInfo.FLAG_SYSTEM != 0
                HomeClaim(it.packageName, info.priority, system)
            }
        }
        val chosen = pm.resolveActivity(home, PackageManager.MATCH_DEFAULT_ONLY)?.activityInfo?.packageName
        HomeScreens.of(claims, chosen)
    }

    fun contains(packageName: String?): Boolean = packageName != null && packageName in reading.read()

    /** The whole set, for the list of what the lock and the allow-list leave alone. */
    val all: Set<String> get() = reading.read()
}
