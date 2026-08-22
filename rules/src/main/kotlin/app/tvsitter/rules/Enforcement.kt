/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
package app.tvsitter.rules

/** What the budget says should be happening. */
enum class BudgetVerdict {
    /** Nothing to do: there is time left, or there is no limit. */
    WITHIN,

    /**
     * Close to the end. Worth saying so without covering anything.
     *
     * A limit that arrives with no warning reads as a punishment, and leaves a child unable
     * to finish what they were doing — which is the difference between a rule and an ambush.
     */
    WARN,

    /** The day's allowance is gone. */
    SPENT,
}

/**
 * Turns "how much is left" into "what should happen".
 *
 * Deliberately a pure function of one number: keeping the decision here rather than in the
 * service means the boundaries can be tested without a television, and the service only has
 * to act on the answer.
 */
object BudgetEnforcement {

    /** Five minutes. Long enough to finish a scene, short enough to still mean "soon". */
    const val DEFAULT_WARNING_SECONDS: Long = 300

    fun verdictFor(remainingSeconds: Long?, warningSeconds: Long = DEFAULT_WARNING_SECONDS): BudgetVerdict = when {
        // No limit in force. Not the same as plenty of time left, but it calls for the same
        // amount of doing nothing.
        remainingSeconds == null -> BudgetVerdict.WITHIN
        remainingSeconds <= 0 -> BudgetVerdict.SPENT
        remainingSeconds <= warningSeconds -> BudgetVerdict.WARN
        else -> BudgetVerdict.WITHIN
    }
}
