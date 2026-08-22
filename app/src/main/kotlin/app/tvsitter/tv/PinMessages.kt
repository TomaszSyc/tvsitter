/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.tv

import android.content.Context
import app.tvsitter.rules.ParentPin
import app.tvsitter.rules.PinOutcome
import kotlin.math.ceil

/**
 * What to say after a PIN entry, or null when there is nothing to say because it was right.
 *
 * One function rather than a copy on each screen: the lock screen and [PinActivity] answer the
 * same five outcomes, and two lists of strings would drift until they contradicted each other
 * about how many attempts are left.
 */
fun Context.pinMessage(outcome: PinOutcome): String? = when (outcome) {
    PinOutcome.Accepted -> null

    is PinOutcome.Wrong -> resources.getQuantityString(
        R.plurals.pin_wrong,
        outcome.attemptsRemaining,
        outcome.attemptsRemaining,
    )

    is PinOutcome.LockedOut -> {
        // Rounded up and never below one: "wait 0 minutes" in front of a keypad that refuses
        // to take anything is worse than a minute that turns out to be forty seconds.
        val minutes = ceil(outcome.secondsRemaining / SECONDS_PER_MINUTE).toInt().coerceAtLeast(1)
        resources.getQuantityString(R.plurals.pin_locked_out, minutes, minutes)
    }

    PinOutcome.NotSet -> getString(R.string.pin_not_set)

    PinOutcome.NewPinRejected -> getString(R.string.pin_length, ParentPin.LENGTH)
}

private const val SECONDS_PER_MINUTE = 60.0
