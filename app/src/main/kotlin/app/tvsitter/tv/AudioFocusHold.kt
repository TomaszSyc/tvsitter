/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.tv

import android.content.Context
import android.media.AudioAttributes
import android.media.AudioFocusRequest
import android.media.AudioManager
import android.util.Log

/**
 * Takes audio focus while the lock is up, so whatever was playing stops.
 *
 * Covering the screen and ending a media session are separate jobs, and the overlay only ever
 * did the first: with the lock over a playing film the sound carried on, which leaves anything
 * audio-led — music, a podcast, a let's-play — not restricted at all. See #16.
 *
 * Audio focus is the platform's own mechanism for this, and it is reversible: a well-behaved
 * media app pauses when it loses focus and nothing has been destroyed, so unlocking leaves the
 * device exactly as usable as before.
 *
 * `AUDIOFOCUS_GAIN` rather than one of the transient forms. Transient focus asks other apps to
 * pause and resume afterwards, which for a lock is the wrong shape: a child should press play
 * again themselves once the lock is gone, rather than have a film start up on its own.
 *
 * Two things it cannot do, both worth knowing rather than discovering. An app that ignores
 * focus loss keeps playing, which is why the listener below logs when focus is taken back. And
 * an external HDMI source is not an Android media session at all (D12), so its sound is out of
 * reach of this entirely.
 */
class AudioFocusHold(context: Context) {

    private val audioManager = context.getSystemService(AudioManager::class.java)
    private var request: AudioFocusRequest? = null

    val isHeld: Boolean get() = request != null

    fun claim() {
        if (request != null) return
        val manager = audioManager ?: run {
            Log.w(EnforcerService.TAG, "audio: no AudioManager, playback will not be stopped")
            return
        }

        val focusRequest = AudioFocusRequest.Builder(AudioManager.AUDIOFOCUS_GAIN)
            .setAudioAttributes(
                AudioAttributes.Builder()
                    // Presenting as media on purpose: that is the focus other players yield
                    // to. A sonification usage would make them duck rather than stop, and a
                    // film at low volume behind a lock screen is still a film.
                    .setUsage(AudioAttributes.USAGE_MEDIA)
                    .setContentType(AudioAttributes.CONTENT_TYPE_MOVIE)
                    .build(),
            )
            // Explicitly not accepting a delayed grant. A lock that silences the television a
            // few seconds later, once some other app finishes, is a lock that failed.
            .setAcceptsDelayedFocusGain(false)
            .setOnAudioFocusChangeListener { change -> onFocusChanged(change) }
            .build()

        val result = manager.requestAudioFocus(focusRequest)
        if (result == AudioManager.AUDIOFOCUS_REQUEST_GRANTED) {
            request = focusRequest
            Log.i(EnforcerService.TAG, "audio: focus held, playback should stop")
        } else {
            Log.w(EnforcerService.TAG, "audio: focus refused ($result), playback may continue")
        }
    }

    fun release() {
        val held = request ?: return
        request = null
        audioManager?.abandonAudioFocusRequest(held)
        Log.i(EnforcerService.TAG, "audio: focus released")
    }

    private fun onFocusChanged(change: Int) {
        // Losing focus while the lock is up means something else claimed the speakers, so the
        // silence did not hold. Logged rather than fought over: taking it back in a loop would
        // be two apps arguing, and the escalation for that is displacing the player, not
        // out-shouting it.
        if (change == AudioManager.AUDIOFOCUS_LOSS ||
            change == AudioManager.AUDIOFOCUS_LOSS_TRANSIENT
        ) {
            Log.w(EnforcerService.TAG, "audio: focus taken back ($change), something is playing")
        }
    }
}
