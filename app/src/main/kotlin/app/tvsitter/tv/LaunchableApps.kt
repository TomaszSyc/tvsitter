/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.tv

import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.SystemClock
import android.util.Log

/**
 * Which apps a child could actually open, package to label.
 *
 * Usage answers "what has been watched". This answers "what is there to watch", and an
 * allow-list needs the second one: built from usage it could only ever refuse an app somebody
 * had already run, which is never the app installed this afternoon and not opened yet (#102).
 *
 * The question asked is "which packages have a launcher entry point", not "which packages are
 * installed". [PackageManager.getInstalledApplications] answers a Google TV with several hundred
 * entries — system services, providers, vendor plumbing, an input framework per manufacturer —
 * and almost none of them is something a remote control can start. Resolving `ACTION_MAIN`
 * instead gives the set the home screen is built from, which is the set the child sees.
 *
 * Both launcher categories, because they are two different populations. `LEANBACK_LAUNCHER` is
 * what an Android TV app declares and what the home row shows; `LAUNCHER` is what a sideloaded
 * phone app declares, and those are reachable from a sideloaded launcher. Asking only the first
 * would leave the apps most likely to want refusing as the ones nobody can tick.
 *
 * Labels come from [AppLabels] rather than from each `ResolveInfo`, so a package is called the
 * same thing here as in `per_app_names`. An activity label and an application label differ often
 * enough that two names for one package on one dashboard would read as a bug.
 *
 * Re-resolved on a timer, unlike [ScreenSaverPackages] and [SettingsPackages], which resolve once
 * because their answer cannot change while the process lives. This one can, and installing an app
 * is precisely the event an allow-list has to hear about — this service runs for weeks between
 * restarts, so resolving once would mean a new app stayed untickable until something killed it.
 *
 * The first resolve is the expensive one, because it loads a label per app; every later one finds
 * them in [AppLabels] and costs two calls to the package manager. That is why the answer is held
 * rather than fetched per payload, and why it is not resolved eagerly in the constructor: the
 * first call falls on whoever builds the first state payload, which is a service that has not
 * connected to a broker yet, rather than on the boot path.
 */
class LaunchableApps(context: Context, private val labels: AppLabels) {

    private val packageManager: PackageManager = context.packageManager

    private var cached: Map<String, String> = emptyMap()
    private var resolvedAtMs = 0L

    /**
     * The whole set, for the state payload, refreshed when the last answer has gone stale.
     *
     * A property rather than a method because it is a reading, and synchronised because the
     * payload is built from more than one thread — two callers arriving together should wait for
     * one query rather than each run their own.
     */
    @get:Synchronized
    val all: Map<String, String>
        get() {
            // elapsedRealtime rather than wall time: a television whose clock jumps is a case
            // this project already handles (see TrustedClock), and a jump must not strand this
            // set for hours or refresh it in a loop.
            val now = SystemClock.elapsedRealtime()
            if (resolvedAtMs == 0L || now - resolvedAtMs >= STALE_AFTER_MS) {
                cached = resolve()
                resolvedAtMs = now
            }
            return cached
        }

    private fun resolve(): Map<String, String> {
        val found = runCatching {
            (launchersFor(Intent.CATEGORY_LEANBACK_LAUNCHER) + launchersFor(Intent.CATEGORY_LAUNCHER))
                .distinct()
                // Sorted, so two payloads holding the same set are the same bytes.
                .sorted()
                .associateWith { labels.labelOf(it) }
        }.getOrElse {
            // A television that cannot enumerate is a television with no allow-list screen, not
            // a broken one. So this degrades to nothing rather than taking the payload with it.
            Log.w(EnforcerService.TAG, "could not list launchable apps; none will be offered", it)
            emptyMap()
        }

        // The count rather than the names: this is the line that says whether package visibility
        // is working at all, and an empty answer is otherwise silent.
        Log.i(EnforcerService.TAG, "launchable apps: ${found.size}")
        return found
    }

    private fun launchersFor(category: String): List<String> = packageManager
        .queryIntentActivities(Intent(Intent.ACTION_MAIN).addCategory(category), 0)
        .mapNotNull { it.activityInfo?.packageName }

    private companion object {
        /**
         * Five minutes. Long enough that the heartbeat is not querying the package manager every
         * minute, short enough that a parent who installs something and reaches for their phone
         * finds it there.
         */
        const val STALE_AFTER_MS = 300_000L
    }
}
