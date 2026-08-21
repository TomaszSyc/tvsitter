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
import android.os.Handler
import android.os.Looper
import android.os.Process
import android.util.TypedValue
import android.view.Gravity
import android.view.View
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView
import android.provider.Settings as AndroidSettings

/**
 * The first screen anybody meets, so it does two jobs: it pairs the television with Home
 * Assistant, and it says what state everything is in when something is not working.
 *
 * Opening it also starts the enforcer. Nothing else does until the next reboot — a foreground
 * service is not started by installing the app, where the accessibility service this replaced
 * was started by the system the moment it was enabled.
 */
class SetupActivity : Activity() {

    private lateinit var heading: TextView
    private lateinit var pin: TextView
    private lateinit var pinNote: TextView
    private lateinit var pairButton: Button
    private lateinit var report: TextView

    private val refresh = Handler(Looper.getMainLooper())
    private val tick = object : Runnable {
        override fun run() {
            render()
            refresh.postDelayed(this, REFRESH_MS)
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        heading = textView(sizeSp = 30f, color = Color.WHITE)
        // Read from a sofa, several metres away, so the code is the largest thing on screen.
        pin = textView(sizeSp = 72f, color = ACCENT)
        pinNote = textView(sizeSp = 16f, color = MUTED)
        report = textView(sizeSp = 15f, color = MUTED)
        pairButton = Button(this).apply {
            text = getString(R.string.pair_start)
            setOnClickListener { EnforcerService.instance?.requestPairing() }
        }

        setContentView(
            LinearLayout(this).apply {
                orientation = LinearLayout.VERTICAL
                gravity = Gravity.START
                setBackgroundColor(BACKDROP)
                setPadding(PADDING, PADDING, PADDING, PADDING)
                addView(textView(sizeSp = 22f, color = MUTED).apply { text = getString(R.string.app_name) })
                addView(heading)
                addView(pin)
                addView(pinNote)
                addView(pairButton)
                addView(report)
            },
        )
    }

    override fun onResume() {
        super.onResume()
        EnforcerService.start(this)
        tick.run()
    }

    override fun onPause() {
        refresh.removeCallbacks(tick)
        super.onPause()
    }

    private fun render() {
        val service = EnforcerService.instance
        val code = service?.pairingPin

        if (code != null) {
            heading.text = getString(R.string.pair_heading)
            pin.text = code.chunked(PIN_GROUP).joinToString(separator = " ")
            pin.visibility = View.VISIBLE
            pinNote.text = buildString {
                appendLine(getString(R.string.pair_instructions))
                append(getString(R.string.pair_expires, service.pairingSecondsRemaining()))
            }
            pairButton.visibility = View.GONE
        } else {
            heading.text = getString(R.string.pair_heading)
            pin.visibility = View.GONE
            pinNote.text = getString(R.string.pair_instructions)
            pairButton.visibility = View.VISIBLE
        }

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
            appendLine(getString(R.string.setup_service_running, if (service != null) yes else no))
            appendLine(
                getString(
                    R.string.setup_overlay,
                    if (AndroidSettings.canDrawOverlays(this@SetupActivity)) yes else no,
                ),
            )
            appendLine(getString(R.string.setup_usage_access, if (hasUsageStatsAccess()) yes else no))
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

    private fun textView(sizeSp: Float, color: Int) = TextView(this).apply {
        setTextColor(color)
        setTextSize(TypedValue.COMPLEX_UNIT_SP, sizeSp)
    }

    private companion object {
        const val PADDING = 48
        const val REFRESH_MS = 1000L
        const val PIN_GROUP = 3
        const val BACKDROP = 0xFF0B1017.toInt()
        const val ACCENT = 0xFF4CC2A5.toInt()
        const val MUTED = 0xFFB9C6D2.toInt()
    }
}
