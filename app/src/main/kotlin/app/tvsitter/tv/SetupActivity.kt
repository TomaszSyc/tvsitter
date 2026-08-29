/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.tv

import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.View
import android.widget.FrameLayout
import android.widget.LinearLayout
import androidx.activity.ComponentActivity
import androidx.activity.OnBackPressedCallback

/**
 * The shell: a rail down the side, one destination at a time beside it.
 *
 * It used to be everything in one column — a few facts, two buttons, then more facts — which is
 * what somebody using it called chaos, and they were right (#108, #109). The platform's guidance
 * is specific about the alternative: a permanently visible rail, five or six destinations at
 * most, a fixed start destination, and back that always returns to the previous one and never
 * gates the exit.
 *
 * Three destinations, which is comfortably under the ceiling: what is happening now, what has
 * been watched, and what can be changed.
 */
class SetupActivity : ComponentActivity() {

    /**
     * Reads device-encrypted storage, so it answers whether there is a PIN even before the
     * service has started.
     */
    private val parentPin by lazy { PinKeeper(this) }

    private lateinit var rail: NavigationRail
    private lateinit var content: FrameLayout
    private lateinit var today: TodayPanel
    private lateinit var stats: StatsPanel
    private lateinit var settings: SettingsPanel

    private var showing = Destination.TODAY

    private val refresh = Handler(Looper.getMainLooper())
    private val tick = object : Runnable {
        override fun run() {
            render()
            refresh.postDelayed(this, REFRESH_MS)
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        today = TodayPanel(this)
        stats = StatsPanel(this)
        settings = SettingsPanel(this, parentPin)
        content = FrameLayout(this)
        rail = NavigationRail(this) { go(it) }

        setContentView(
            LinearLayout(this).apply {
                orientation = LinearLayout.HORIZONTAL
                setBackgroundColor(TvStyle.BACKDROP)
                addView(
                    rail,
                    LinearLayout.LayoutParams(
                        LinearLayout.LayoutParams.WRAP_CONTENT,
                        LinearLayout.LayoutParams.MATCH_PARENT,
                    ),
                )
                addView(
                    content,
                    LinearLayout.LayoutParams(
                        LinearLayout.LayoutParams.MATCH_PARENT,
                        LinearLayout.LayoutParams.MATCH_PARENT,
                    ),
                )
            },
        )
        onBackPressedDispatcher.addCallback(this, goBack)
        go(Destination.TODAY)
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

    /**
     * Back, in the order the guidance asks for.
     *
     * From the content, back is a step out to the rail rather than out of the app — somebody
     * deep in Settings has somewhere to go that is not the home screen. From the rail, back goes
     * to the start destination, and from the start destination it leaves. Nothing asks "are you
     * sure": never gate an exit.
     */
    private val goBack = object : OnBackPressedCallback(true) {
        override fun handleOnBackPressed() {
            when {
                content.hasFocus() -> rail.focusCurrent()
                showing != Destination.TODAY -> go(Destination.TODAY)
                else -> {
                    // Nothing left to step back through, so leave. Never gate an exit.
                    isEnabled = false
                    onBackPressedDispatcher.onBackPressed()
                }
            }
        }
    }

    private fun go(destination: Destination) {
        showing = destination
        rail.select(destination)
        content.removeAllViews()
        content.addView(
            when (destination) {
                Destination.TODAY -> today.view
                Destination.STATISTICS -> stats.view
                Destination.SETTINGS -> settings.view
            },
        )
        render()
        // The rail keeps the focus, on every destination. Settings used to jump into its own
        // content, which collapsed the rail on that screen and nowhere else — one screen behaving
        // unlike the other two is exactly the thing this shell exists to stop. Right, or down,
        // goes into the content when there is anything there to reach.
        rail.focusCurrent()
    }

    private fun render() {
        when (showing) {
            Destination.TODAY -> today.refresh()
            Destination.STATISTICS -> stats.refresh()
            Destination.SETTINGS -> settings.refresh()
        }
    }

    private companion object {
        /** Often enough that a pairing countdown moves, rarely enough to be free. */
        const val REFRESH_MS = 1_000L
    }
}
