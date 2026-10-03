/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.rules

import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test
import java.util.concurrent.CountDownLatch
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit

class PinDeskTest {

    private val now = 1_787_400_000_000
    private val salt = "0f1e2d3c4b5a69788796a5b4c3d2e1f0"

    /** Slow enough that guesses submitted together are still being derived when the next arrives. */
    private val stored = ParentPin.create("4829", salt, iterations = 20_000)

    private class MemoryLedger(override var hash: PinHash?) : PinLedger {
        override var lockout: PinLockout = PinLockout()
    }

    private fun desk(ledger: PinLedger) = PinDesk(ledger, lock = ledger, clock = { now })

    @Test
    fun `guesses typed while one is being checked still run out after five`() {
        val ledger = MemoryLedger(stored)
        val desk = desk(ledger)
        val guesses = 12
        val start = CountDownLatch(1)
        val pool = Executors.newFixedThreadPool(guesses)
        val entries = (0 until guesses).map { i ->
            pool.submit<PinEntry> {
                start.await()
                desk.verify("%04d".format(i))
            }
        }
        start.countDown()
        val results = entries.map { it.get(30, TimeUnit.SECONDS) }
        pool.shutdown()

        // Read together, every guess saw a fresh counter and the keypad never shut.
        assertEquals(PinGuard.MAX_FAILURES - 1, results.count { it.outcome is PinOutcome.Wrong })
        assertEquals(1, results.count { it.shutTheKeypad }, "the lockout alarm went out more than once")
        assertEquals(1, ledger.lockout.lockouts)
        assertTrue(ledger.lockout.lockedUntilMs > now)
    }

    @Test
    fun `the right PIN is refused once the keypad has shut`() {
        val ledger = MemoryLedger(stored)
        val desk = desk(ledger)
        repeat(PinGuard.MAX_FAILURES) { desk.verify("0000") }

        assertTrue(desk.verify("4829").outcome is PinOutcome.LockedOut)
    }

    @Test
    fun `a change spends from the same counter and stores the new PIN`() {
        val ledger = MemoryLedger(stored)
        val desk = desk(ledger)
        desk.verify("0000")

        val changed = desk.change("4829", "1357")

        assertEquals(PinOutcome.Accepted, changed.outcome)
        assertEquals(PinLockout(), ledger.lockout)
        assertEquals(PinOutcome.Accepted, desk.verify("1357").outcome)
    }

    @Test
    fun `a change that shuts the keypad says so`() {
        val ledger = MemoryLedger(stored)
        val desk = desk(ledger)
        repeat(PinGuard.MAX_FAILURES - 1) { desk.verify("0000") }

        assertTrue(desk.change("0000", "1357").shutTheKeypad)
    }

    @Test
    fun `a replaced PIN forgives the wrong guesses at the old one`() {
        val ledger = MemoryLedger(stored)
        val desk = desk(ledger)
        repeat(PinGuard.MAX_FAILURES) { desk.verify("0000") }

        desk.replace(null)

        assertEquals(PinLockout(), ledger.lockout)
        assertEquals(PinOutcome.NotSet, desk.verify("4829").outcome)
    }
}
