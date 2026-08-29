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
import android.widget.ScrollView
import android.widget.TextView
import app.tvsitter.rules.Rules
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put

/**
 * Everything a parent might have to change while standing at the television.
 *
 * Its own destination rather than a block under the status, because it is the half of the product
 * Home Assistant normally owns and the half that has to keep working when Home Assistant is not
 * there (#112). D25 has been pointing at this from the other side since M5: the enforcing half is
 * already independent, and until now the editing half was not — every rule could only be changed
 * from somewhere else.
 *
 * The rules sit behind the parent PIN, the same door pairing sits behind (#98). Proving it once
 * covers the visit rather than each press: three questions in a row, each with two seconds of
 * hashing, is how a parent gives up halfway through. Leaving the screen ends it, because the
 * whole panel is rebuilt on the way back in.
 */
class SettingsPanel(private val activity: Activity, private val parentPin: PinKeeper, private val prove: () -> Unit) {

    private var proved = false

    private val heading = text(TvStyle.HEADING_SP, TvStyle.TEXT)
    private val code = text(PAIRING_CODE_SP, TvStyle.ACCENT)
    private val note = text(TvStyle.SMALL_SP, TvStyle.MUTED)
    private val trouble = text(TvStyle.BODY_SP, TvStyle.WARN)
    private val footer = text(TvStyle.SMALL_SP, TvStyle.MUTED)
    private val lockedNote = text(TvStyle.BODY_SP, TvStyle.MUTED)

    private val unlockButton = button { prove() }
    private val limitButton = button { chooseDailyLimit() }
    private val sleepButton = button { chooseSleepTimer() }
    private val blockButton = button { toggleSettingsBlock() }

    private val pairButton = button {
        // Through the PIN screen, which opens the window itself once the PIN is right, or
        // straight away when there is no PIN to ask for. A pairing code is on a fifty-inch screen
        // in front of the person the PIN exists to keep out, and after pairing the television
        // takes its commands — unlock included — from whichever broker answered (#98).
        activity.startActivity(
            Intent(activity, PinActivity::class.java).putExtra(PinActivity.EXTRA_FOR_PAIRING, true),
        )
    }

    private val pinButton = button {
        activity.startActivity(Intent(activity, PinActivity::class.java))
    }.apply { setText(R.string.pin_change) }

    private val rules = column(limitButton, sleepButton, blockButton)

    val view: View = ScrollView(activity).apply {
        isFillViewport = true
        TvStyle.letFocusOverflow(this)
        addView(
            LinearLayout(activity).apply {
                orientation = LinearLayout.VERTICAL
                setPadding(TvStyle.OVERSCAN_PX, TvStyle.OVERSCAN_PX, TvStyle.OVERSCAN_PX, TvStyle.OVERSCAN_PX)
                TvStyle.letFocusOverflow(this)
                addView(section(R.string.set_section_rules))
                addView(lockedNote)
                addView(column(unlockButton))
                addView(rules)
                addView(section(R.string.set_section_tv))
                addView(heading)
                addView(code)
                addView(note)
                addView(column(pairButton, pinButton))
                addView(section(R.string.set_section_diag))
                addView(trouble)
                addView(footer)
            },
        )
    }

    /** Called when the PIN screen answered yes, which opens the rules for this visit. */
    fun unlock() {
        proved = true
        refresh()
        limitButton.requestFocus()
    }

    fun refresh() {
        val service = EnforcerService.instance
        showRules(service)
        showPairing(service)

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

    /**
     * The rules, or the reason they are not on offer.
     *
     * A television with no PIN has nobody to keep out — the same reading pairing takes on a first
     * run — so the rules are simply there. Once there is a PIN, they are behind it.
     */
    private fun showRules(service: EnforcerService?) {
        val open = proved || !parentPin.isSet
        rules.visibility = if (open && service != null) View.VISIBLE else View.GONE
        unlockButton.visibility = if (open || service == null) View.GONE else View.VISIBLE
        unlockButton.setText(R.string.set_unlock)

        lockedNote.setText(if (service == null) R.string.set_no_service else R.string.set_locked_note)
        lockedNote.visibility = if (open && service != null) View.GONE else View.VISIBLE
        if (service != null) showValues(service)
    }

    /** What each rule currently says, on the button that changes it. */
    private fun showValues(service: EnforcerService) {
        limitButton.text = row(R.string.set_daily_limit, lengthOrNone(service.rules.dailyLimitSeconds))
        sleepButton.text = row(
            R.string.set_sleep_timer,
            service.sleepInMinutes.takeIf { it > 0 }
                ?.let { TvStyle.length(activity, it * SECONDS_PER_MINUTE) }
                ?: activity.getString(R.string.set_sleep_off),
        )
        blockButton.text = row(
            R.string.set_block_settings,
            activity.getString(if (service.rules.settingsBlocked) R.string.set_on else R.string.set_off),
        )
    }

    private fun showPairing(service: EnforcerService?) {
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
    }

    /**
     * The day's allowance, written the way Home Assistant writes it.
     *
     * No limit is a null rather than a zero, because zero minutes is a real thing a parent may
     * mean — no viewing today — and the two must stay tellable apart. That is the same convention
     * the contract has carried since M4, and going through [EnforcerService.changeRules] means
     * there is one way of writing a rule rather than two.
     */
    private fun chooseDailyLimit() {
        val service = EnforcerService.instance ?: return
        ChoiceDialog.show(
            activity,
            activity.getString(R.string.set_daily_limit),
            listOf(Choice<Int?>(activity.getString(R.string.set_no_limit), null)) +
                LIMIT_MINUTES.map { Choice<Int?>(TvStyle.length(activity, it * SECONDS_PER_MINUTE), it) },
            service.rules.dailyLimitSeconds?.let { (it / SECONDS_PER_MINUTE).toInt() },
        ) { minutes ->
            service.changeRules(
                buildJsonObject {
                    if (minutes == null) {
                        put(Rules.KEY_DAILY_LIMIT, JsonNull)
                    } else {
                        put(Rules.KEY_DAILY_LIMIT, minutes.toLong() * SECONDS_PER_MINUTE)
                    }
                },
            )
            refresh()
        }
    }

    /** One evening's decision, so it is a command rather than a rule — D30, from M4. */
    private fun chooseSleepTimer() {
        val service = EnforcerService.instance ?: return
        ChoiceDialog.show(
            activity,
            activity.getString(R.string.set_sleep_timer),
            listOf(Choice(activity.getString(R.string.set_sleep_off), 0)) +
                SLEEP_MINUTES.map { Choice(TvStyle.length(activity, it * SECONDS_PER_MINUTE), it) },
            service.sleepInMinutes,
        ) { minutes ->
            service.sleepInMinutes = minutes
            refresh()
        }
    }

    private fun toggleSettingsBlock() {
        val service = EnforcerService.instance ?: return
        service.changeRules(
            buildJsonObject { put(Rules.KEY_BLOCK_SETTINGS, !service.rules.settingsBlocked) },
        )
        refresh()
    }

    private fun lengthOrNone(seconds: Long?): String = seconds
        ?.let { TvStyle.length(activity, it.toInt()) }
        ?: activity.getString(R.string.set_no_limit)

    private fun row(labelRes: Int, value: String) =
        activity.getString(R.string.set_row, activity.getString(labelRes), value)

    private fun button(onPress: () -> Unit) = Button(activity).apply {
        setOnClickListener { onPress() }
        TvStyle.dress(this)
    }

    /**
     * A stack of buttons, each as wide as the panel.
     *
     * Down the screen rather than across, because these are categories of thing rather than items
     * within one — the axis the platform's guidance asks for, and the axis a list of settings is
     * read in anywhere else.
     */
    private fun column(vararg buttons: Button) = LinearLayout(activity).apply {
        orientation = LinearLayout.VERTICAL
        TvStyle.letFocusOverflow(this)
        buttons.forEach { button ->
            button.gravity = android.view.Gravity.CENTER_VERTICAL or android.view.Gravity.START
            addView(
                button,
                LinearLayout.LayoutParams(ROW_WIDTH_PX, LinearLayout.LayoutParams.WRAP_CONTENT).apply {
                    setMargins(TvStyle.GAP_PX, TvStyle.GAP_PX / 2, TvStyle.GAP_PX, TvStyle.GAP_PX / 2)
                },
            )
        }
    }

    private fun section(labelRes: Int) = text(TvStyle.SMALL_SP, TvStyle.ACCENT).apply {
        setText(labelRes)
        setPadding(0, TvStyle.OVERSCAN_PX / 2, 0, TvStyle.GAP_PX / 2)
        isAllCaps = true
        letterSpacing = SECTION_TRACKING
    }

    private fun text(sizeSp: Float, colour: Int) = TextView(activity).apply {
        setTextColor(colour)
        setTextSize(android.util.TypedValue.COMPLEX_UNIT_SP, sizeSp)
    }

    private companion object {
        /** Read from a sofa several metres away, so the code is the largest thing on screen. */
        const val PAIRING_CODE_SP = 72f
        const val SECONDS_PER_MINUTE = 60
        const val ROW_WIDTH_PX = 900
        const val SECTION_TRACKING = 0.12f

        /**
         * Round numbers a parent would say out loud, not every multiple of five.
         *
         * A list is picked from with a D-pad, so its length is what it costs: thirty entries is a
         * minute of pressing down to reach three hours.
         */
        val LIMIT_MINUTES = listOf(15, 30, 45, 60, 90, 120, 150, 180, 240, 300, 360)
        val SLEEP_MINUTES = listOf(15, 30, 45, 60, 90, 120)
    }
}
