/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.rules

/** What the television looked like over one interval. */
data class Attention(
    val screenOn: Boolean,
    /** A screen saver was in front — D20's case, and free of charge. */
    val screenSaver: Boolean,
    /** Something was playing audio through Android. */
    val playing: Boolean,
    /** The foreground app is a television or HDMI input rather than an ordinary app. */
    val tvInput: Boolean,
    /** How long since anything last happened: playback starting, or the app changing. */
    val quietForMs: Long,
)

/**
 * Whether an interval is charged to the child.
 *
 * "The screen is on" turned out to be too generous. Measured on the Philips: the set's own
 * image-sticking protection puts a drifting logo over a static screen after a few minutes, and
 * seven minutes of that were billed to the day's budget while nobody was in the room. D20 had
 * already dealt with the Android screen saver, but that one is a `DreamService` and this is a
 * window from the TV's firmware — invisible to the same trick, and invisible to everything
 * else this app can see: the foreground app never changes, the screen still reports on, and
 * this television emits no user-interaction events at all.
 *
 * So the question becomes "is anything actually happening", answered from what is available:
 *
 * - something is playing, which covers a film, a game and — measured — an HDMI source, whose
 *   sound does reach Android through the input service
 * - or the last thing that happened was recent enough that somebody is plainly still using the
 *   set: choosing a programme, reading a description, walking through a menu
 *
 * The grace period is what stops this being unfair. Browsing is television time and has to be
 * charged; a television left on the launcher while everyone is at dinner is not. Five minutes
 * sits between the two, and close to when the set's own protection gives up on the room.
 *
 * A TV or HDMI input always counts while the screen is on. Its audio does reach Android here,
 * but that is one television's behaviour rather than a promise, and the failure this guards
 * against — a console session quietly costing nothing — is the worse of the two.
 */
object AttentionRule {

    /** Long enough for browsing, short enough that an empty room stops paying. */
    const val GRACE_MS: Long = 5 * 60 * 1000

    fun isWatching(attention: Attention, graceMs: Long = GRACE_MS): Boolean {
        if (!attention.screenOn) return false
        if (attention.screenSaver) return false
        if (attention.tvInput) return true
        if (attention.playing) return true
        return attention.quietForMs < graceMs
    }
}
