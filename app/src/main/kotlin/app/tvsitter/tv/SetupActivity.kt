/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.tv

import android.app.Activity
import android.app.AppOpsManager
import android.content.Intent
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
    private lateinit var pinButton: Button
    private lateinit var report: TextView

    /**
     * Reads device-encrypted storage, so it answers whether there is a PIN even before the
     * service has started.
     */
    private val parentPin by lazy { PinKeeper(this) }

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
            // Through the PIN screen, which opens the window itself once the PIN is right, or
            // straight away when there is no PIN to ask for. A pairing code is on a fifty-inch
            // screen in front of the person the PIN exists to keep out, and after pairing the
            // television takes its commands — unlock included — from whichever broker answered
            // (#98).
            setOnClickListener {
                startActivity(
                    Intent(this@SetupActivity, PinActivity::class.java)
                        .putExtra(PinActivity.EXTRA_FOR_PAIRING, true),
                )
            }
        }
        // Only ever offered when a PIN already exists: the change screen asks for the current
        // one, and there is no first PIN to be had at the television.
        pinButton = Button(this).apply {
            text = getString(R.string.pin_change)
            setOnClickListener { startActivity(Intent(this@SetupActivity, PinActivity::class.java)) }
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
                addView(pinButton)
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
        val copy = pairingCopy(EnforcerService.instance)

        heading.text = copy.heading
        pinNote.text = copy.note
        pin.text = copy.pin.orEmpty()
        pin.visibility = if (copy.pin != null) View.VISIBLE else View.GONE
        pairButton.text = copy.buttonLabel.orEmpty()
        pairButton.visibility = if (copy.buttonLabel != null) View.VISIBLE else View.GONE
        pinButton.visibility = if (parentPin.isSet) View.VISIBLE else View.GONE

        report.text = buildReport()
    }

    /** What the screen says, as a table rather than as branches that each set four fields. */
    private data class Copy(
        val heading: String,
        val note: String,
        val pin: String? = null,
        val buttonLabel: String? = null,
    )

    /**
     * Four states, where there used to be two.
     *
     * A successful pairing used to drop straight back to "press the button to pair", because
     * the only thing the screen looked at was whether a PIN existed — so the one screen anybody
     * sees said nothing about having worked. A window that failed to open looked identical.
     */
    private fun pairingCopy(service: EnforcerService?): Copy {
        // Only while there is time left on it. The window closes itself now, but a second of
        // timer jitter should not put a dead code on a fifty-inch screen either.
        val code = service?.pairingPin?.takeIf { service.pairingSecondsRemaining() > 0 }
        return when {
            service == null -> invitation()

            code != null -> Copy(
                heading = getString(R.string.pair_heading),
                note = getString(R.string.pair_instructions) + "\n" +
                    getString(R.string.pair_expires, service.pairingSecondsRemaining()),
                pin = code.chunked(PIN_GROUP).joinToString(separator = " "),
            )

            // Ahead of the paired state on purpose. Somebody pressed a button and nothing
            // happened, which is the worse of the two things to be silent about — but the
            // heading still says "Paired" when it is, because that stayed true.
            service.lastPairingFailed -> Copy(
                heading = getString(
                    if (service.isPaired) R.string.pair_paired else R.string.pair_heading,
                ),
                note = getString(R.string.pair_failed),
                buttonLabel = getString(
                    if (service.isPaired) R.string.pair_again else R.string.pair_start,
                ),
            )

            // Offer to pair again regardless: a broker moves, and a paired TV is exactly the
            // one that needs to be told about it.
            service.isPaired -> Copy(
                heading = getString(R.string.pair_paired),
                note = getString(
                    if (service.isReporting) R.string.pair_done else R.string.pair_offline,
                ),
                buttonLabel = getString(R.string.pair_again),
            )

            else -> invitation()
        }
    }

    private fun invitation() = Copy(
        heading = getString(R.string.pair_heading),
        note = getString(R.string.pair_instructions),
        buttonLabel = getString(R.string.pair_start),
    )

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
            appendLine(
                getString(R.string.setup_reporting, if (service?.isReporting == true) yes else no),
            )
            // Said out loud because the answer matters most on the evening Home Assistant is
            // unreachable, and that is the worst moment to find out it is "no".
            appendLine(getString(R.string.setup_pin, if (parentPin.isSet) yes else no))
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
