/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.rules

/**
 * Compares two strings without leaking where they differ through timing.
 *
 * Shared by pairing and by the parent PIN. The length is not hidden: a pairing PIN's length is
 * printed on the screen, and a parent PIN's is known to whoever watched it being typed. Only
 * the characters get this treatment.
 */
fun constantTimeEquals(first: String, second: String): Boolean {
    if (first.length != second.length) return false
    var difference = 0
    for (index in first.indices) {
        difference = difference or (first[index].code xor second[index].code)
    }
    return difference == 0
}
