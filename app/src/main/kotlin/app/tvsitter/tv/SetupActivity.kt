/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.tv

import android.app.Activity
import android.app.AppOpsManager
import android.graphics.Color
import android.os.Build
import android.os.Bundle
import android.os.Process
import android.provider.Settings
import android.util.TypedValue
import android.view.Gravity
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView

/**
 * First-run diagnostics screen. At milestone M0 it serves exactly one purpose: showing
 * on the TV itself whether the permissions actually took effect. From M5 it will be
 * hidden from the launcher and gated behind the parent PIN.
 */
class SetupActivity : Activity() {

    private lateinit var report: TextView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        report = TextView(this).apply {
            setTextColor(Color.WHITE)
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 16f)
        }

        setContentView(
            LinearLayout(this).apply {
                orientation = LinearLayout.VERTICAL
                gravity = Gravity.START
                setBackgroundColor(BACKDROP_COLOR)
                setPadding(PADDING, PADDING, PADDING, PADDING)
                addView(
                    TextView(context).apply {
                        text = getString(R.string.app_name)
                        setTextColor(Color.WHITE)
                        setTextSize(TypedValue.COMPLEX_UNIT_SP, 28f)
                    },
                )
                addView(report)
            },
        )
    }

    override fun onResume() {
        super.onResume()
        // Opening this screen is as good a moment as any to make sure the enforcer is up:
        // nothing else revives it, and a user looking at diagnostics is usually looking
        // because something stopped working.
        EnforcerService.start(this)
        report.text = buildReport()
    }

    private fun buildReport(): String {
        val service = EnforcerService.instance
        val yes = getString(R.string.setup_yes)
        val no = getString(R.string.setup_no)
        return buildString {
            appendLine()
            appendLine(
                getString(
                    R.string.setup_device,
                    Build.MANUFACTURER,
                    Build.MODEL,
                    Build.VERSION.SDK_INT,
                ),
            )
            appendLine(getString(R.string.setup_version, BuildConfig.VERSION_NAME))
            appendLine()
            appendLine(getString(R.string.setup_service_running, if (service != null) yes else no))
            appendLine(
                getString(
                    R.string.setup_overlay,
                    if (Settings.canDrawOverlays(this@SetupActivity)) yes else no,
                ),
            )
            appendLine(getString(R.string.setup_usage_access, if (hasUsageStatsAccess()) yes else no))
            appendLine()
            appendLine(
                getString(
                    R.string.setup_foreground,
                    service?.foregroundPackage ?: getString(R.string.setup_unknown),
                ),
            )
            appendLine(getString(R.string.setup_locked, if (service?.isLocked == true) yes else no))
        }
    }

    /**
     * There is no single app-ops call that spans the supported range: `unsafeCheckOpNoThrow`
     * only exists from API 29, and `checkOpNoThrow` is deprecated from that same release.
     * Calling the former unconditionally would throw NoSuchMethodError on Android 8 and 9.
     */
    @Suppress("DEPRECATION")
    private fun hasUsageStatsAccess(): Boolean {
        val appOps = getSystemService(AppOpsManager::class.java) ?: return false
        val mode = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            appOps.unsafeCheckOpNoThrow(
                AppOpsManager.OPSTR_GET_USAGE_STATS,
                Process.myUid(),
                packageName,
            )
        } else {
            appOps.checkOpNoThrow(
                AppOpsManager.OPSTR_GET_USAGE_STATS,
                Process.myUid(),
                packageName,
            )
        }
        return mode == AppOpsManager.MODE_ALLOWED
    }

    private companion object {
        const val PADDING = 48
        const val BACKDROP_COLOR = 0xFF0B1017.toInt()
    }
}
