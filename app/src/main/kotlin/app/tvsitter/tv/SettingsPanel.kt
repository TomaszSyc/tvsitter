/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.tv

import android.app.Activity
import android.content.Intent
import android.view.View
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView

/**
 * Everything a parent might have to change while standing at the television.
 *
 * Its own destination rather than a block under the status, because it is the half of the product
 * that Home Assistant normally owns and the half that has to keep working when Home Assistant is
 * not there (#112). What is here today is pairing, the PIN and what is wrong; the rules follow.
 */
class SettingsPanel(private val activity: Activity, private val parentPin: PinKeeper) {

    private val heading = text(TvStyle.HEADING_SP, TvStyle.TEXT)
    private val code = text(PAIRING_CODE_SP, TvStyle.ACCENT)
    private val note = text(TvStyle.SMALL_SP, TvStyle.MUTED)
    private val trouble = text(TvStyle.BODY_SP, TvStyle.WARN)
    private val footer = text(TvStyle.SMALL_SP, TvStyle.MUTED)

    private val pairButton = Button(activity).apply {
        // Through the PIN screen, which opens the window itself once the PIN is right, or
        // straight away when there is no PIN to ask for. A pairing code is on a fifty-inch screen
        // in front of the person the PIN exists to keep out, and after pairing the television
        // takes its commands — unlock included — from whichever broker answered (#98).
        setOnClickListener {
            activity.startActivity(
                Intent(activity, PinActivity::class.java)
                    .putExtra(PinActivity.EXTRA_FOR_PAIRING, true),
            )
        }
    }

    private val pinButton = Button(activity).apply {
        setText(R.string.pin_change)
        setOnClickListener { activity.startActivity(Intent(activity, PinActivity::class.java)) }
    }

    val view: View = LinearLayout(activity).apply {
        orientation = LinearLayout.VERTICAL
        setPadding(TvStyle.OVERSCAN_PX, TvStyle.OVERSCAN_PX, TvStyle.OVERSCAN_PX, TvStyle.OVERSCAN_PX)
        TvStyle.letFocusOverflow(this)
        listOf(pairButton, pinButton).forEach { TvStyle.dress(it) }
        addView(heading)
        addView(code)
        addView(note)
        addView(
            LinearLayout(activity).apply {
                orientation = LinearLayout.HORIZONTAL
                TvStyle.letFocusOverflow(this)
                listOf(pairButton, pinButton).forEach { button ->
                    addView(
                        button,
                        LinearLayout.LayoutParams(
                            LinearLayout.LayoutParams.WRAP_CONTENT,
                            LinearLayout.LayoutParams.WRAP_CONTENT,
                        ).apply {
                            setMargins(TvStyle.GAP_PX, TvStyle.GAP_PX, TvStyle.GAP_PX, TvStyle.GAP_PX)
                        },
                    )
                }
            },
        )
        addView(trouble)
        addView(footer)
    }

    fun refresh() {
        val service = EnforcerService.instance
        val copy = PairingCopy.of(activity, service)

        heading.text = copy.heading
        note.text = copy.note
        code.text = copy.code.orEmpty()
        code.visibility = if (copy.code != null) View.VISIBLE else View.GONE
        pairButton.text = copy.buttonLabel.orEmpty()
        pairButton.visibility = if (copy.buttonLabel != null) View.VISIBLE else View.GONE
        // Only ever offered when a PIN already exists: the change screen asks for the current
        // one, and there is no first PIN to be had at the television.
        pinButton.visibility = if (parentPin.isSet) View.VISIBLE else View.GONE

        val wrong = Trouble.of(activity, service)
        trouble.text = wrong.joinToString(separator = "\n\n")
        trouble.visibility = if (wrong.isEmpty()) View.GONE else View.VISIBLE

        footer.text = activity.getString(
            R.string.setup_device,
            android.os.Build.MANUFACTURER,
            android.os.Build.MODEL,
            android.os.Build.VERSION.SDK_INT,
        ) + "  ·  " + activity.getString(R.string.setup_version, BuildConfig.VERSION_NAME)
    }

    private fun text(sizeSp: Float, colour: Int) = TextView(activity).apply {
        setTextColor(colour)
        setTextSize(android.util.TypedValue.COMPLEX_UNIT_SP, sizeSp)
    }

    private companion object {
        /** Read from a sofa several metres away, so the code is the largest thing on screen. */
        const val PAIRING_CODE_SP = 72f
    }
}
