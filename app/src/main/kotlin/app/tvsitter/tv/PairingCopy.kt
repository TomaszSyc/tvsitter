/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.tv

import android.content.Context

/**
 * What the pairing part of the screen says, as a table rather than as branches that each set
 * four fields.
 *
 * Lifted out of the activity when the app grew a shape: the states are the same four, and they
 * are about pairing rather than about which screen happens to be showing them.
 */
object PairingCopy {

    data class Copy(val heading: String, val note: String, val code: String? = null, val buttonLabel: String? = null)

    /**
     * Four states, where there used to be two.
     *
     * A successful pairing used to drop straight back to "press the button to pair", because
     * the only thing the screen looked at was whether a PIN existed — so the one screen anybody
     * sees said nothing about having worked. A window that failed to open looked identical.
     */
    fun of(context: Context, service: EnforcerService?): Copy {
        // Only while there is time left on it. The window closes itself now, but a second of
        // timer jitter should not put a dead code on a fifty-inch screen either.
        val pairing = service?.pairingPin?.takeIf { service.pairingSeconds > 0 }
        return when {
            service == null -> invitation(context)

            pairing != null -> Copy(
                heading = context.getString(R.string.pair_heading),
                note = context.getString(R.string.pair_instructions) + "\n" +
                    context.getString(R.string.pair_expires, service.pairingSeconds),
                code = pairing.chunked(PIN_GROUP).joinToString(separator = " "),
            )

            // Ahead of the paired state on purpose. Somebody pressed a button and nothing
            // happened, which is the worse of the two things to be silent about — but the
            // heading still says "Paired" when it is, because that stayed true.
            service.lastPairingFailed -> Copy(
                heading = context.getString(
                    if (service.isPaired) R.string.pair_paired else R.string.pair_heading,
                ),
                note = context.getString(R.string.pair_failed),
                buttonLabel = context.getString(
                    if (service.isPaired) R.string.pair_again else R.string.pair_start,
                ),
            )

            // Offer to pair again regardless: a broker moves, and a paired TV is exactly the
            // one that needs to be told about it.
            service.isPaired -> Copy(
                heading = context.getString(R.string.pair_paired),
                note = context.getString(
                    if (service.isReporting) R.string.pair_done else R.string.pair_offline,
                ),
                buttonLabel = context.getString(R.string.pair_again),
            )

            else -> invitation(context)
        }
    }

    /** Nothing paired yet, or nothing to say beyond how to start. */
    private fun invitation(context: Context) = Copy(
        heading = context.getString(R.string.pair_heading),
        note = context.getString(R.string.pair_instructions),
        buttonLabel = context.getString(R.string.pair_start),
    )

    private const val PIN_GROUP = 3
}
