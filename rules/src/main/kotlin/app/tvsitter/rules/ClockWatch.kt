/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.rules

import kotlin.math.absoluteValue

/**
 * Whether the wall clock moved on its own.
 *
 * The budget day is wall-clock throughout, and date and time are a few D-pad presses away for as
 * long as Settings is reachable. So a spent day can be turned into a fresh one, and the counter
 * would not even notice: it measures differences between readings of the same clock, and a clock
 * that jumps takes the differences with it.
 *
 * The answer is a second clock that nobody can set. `elapsedRealtime` counts since boot and keeps
 * counting in sleep, so the two deltas between a pair of samples should agree. When they do not,
 * the difference is the jump.
 *
 * Pure, and tested on the JVM, because this is the arithmetic that decides whether an evening's
 * allowance comes back.
 */
object ClockWatch {

    /**
     * How far the two may disagree before it counts as a jump.
     *
     * Two minutes. A backwards step is not automatically somebody at the Settings screen — an
     * NTP correction does it, and so does a television that has been unplugged long enough for
     * its clock to drift — so the threshold is minutes rather than seconds. It also has to be
     * larger than any sampling delay: a device coming out of doze can deliver a late tick, and
     * calling that an attack would cry wolf on an ordinary morning.
     */
    const val SLACK_MS: Long = 2 * 60 * 1000

    /**
     * The size of the jump between two samples, or zero when the clocks agree.
     *
     * Positive when the wall clock ran ahead of real time, negative when it fell behind. Both
     * matter: forward buys a new budget day, and backwards keeps the old one from ever ending.
     */
    fun jumpBetween(wallDeltaMs: Long, elapsedDeltaMs: Long, slackMs: Long = SLACK_MS): Long {
        val difference = wallDeltaMs - elapsedDeltaMs
        return if (difference.absoluteValue <= slackMs) 0 else difference
    }

    /**
     * What the clock should be treated as saying, given everything it has jumped so far.
     *
     * The correction accumulates rather than being applied once: somebody who moves the clock
     * twice has moved it twice. What this returns is what the counter is told the time is, so a
     * jump neither rolls the budget day nor hands over an evening — the day stands, and the
     * anchor moves by the time that actually passed.
     */
    fun trusted(wallMs: Long, offsetMs: Long): Long = wallMs - offsetMs
}
