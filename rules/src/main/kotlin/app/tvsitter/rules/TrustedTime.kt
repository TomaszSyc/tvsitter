/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.rules

/**
 * What the time is, after taking off however far somebody has moved the clock by hand.
 *
 * Two readings of the wall clock are compared with the time since boot that passed between them;
 * when they disagree beyond [ClockWatch.SLACK_MS], the difference is a jump and it is taken off
 * everything downstream.
 *
 * Only while the time is set by hand. With network time on, the system owns the clock and a jump is
 * the network putting it right — the television boots with a clock days slow and is corrected a
 * minute later. Read as tampering, that correction left the budget day three days behind and it
 * never rolled over. Moving the clock now means switching network time off in Settings first, and
 * from that moment jumps count again; switching it back on drops what was set by hand.
 */
class TrustedTime(private val onJump: (Long) -> Unit = {}) {

    private var offsetMs = 0L
    private var lastWallMs: Long? = null
    private var lastElapsedMs = 0L

    @Synchronized
    fun now(wallMs: Long, elapsedMs: Long, networkTime: Boolean): Long {
        val last = lastWallMs
        if (networkTime) {
            offsetMs = 0
        } else if (last != null) {
            val jump = ClockWatch.jumpBetween(wallMs - last, elapsedMs - lastElapsedMs)
            if (jump != 0L) {
                offsetMs += jump
                onJump(jump)
            }
        }
        lastWallMs = wallMs
        lastElapsedMs = elapsedMs
        return ClockWatch.trusted(wallMs, offsetMs)
    }
}
