/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
plugins {
    alias(libs.plugins.android.application) apply false
    alias(libs.plugins.kotlin.jvm) apply false
    alias(libs.plugins.kotlin.serialization) apply false
    alias(libs.plugins.spotless)
    alias(libs.plugins.detekt) apply false
}

// Spotless is configured once at the root and reaches into every module, which keeps the
// module build files free of formatting plumbing.
//
// Run it in its own invocation, as the CI workflow does: `./gradlew spotlessCheck` and then
// `./gradlew detekt :app:lintDebug :rules:test`. Combining them in one command intermittently
// fails with "Could not read path .../app/build/intermediates/.../Something.class", because
// Spotless walks the project tree while a compile triggered by the same build is rewriting
// those directories. The targetExclude entries below do not prevent it — the walk happens
// anyway — and it only bites on the first run after a source change, which is what makes it
// look like a flake rather than a race.
spotless {
    kotlin {
        target("**/*.kt")
        targetExclude("**/build/**")
        // The style has to be passed explicitly: Spotless does not forward .editorconfig
        // to ktlint, and ktlint's default "ktlint_official" style rewrites code rather than
        // formatting it — it splits two-parameter signatures across lines and wraps every
        // when branch in braces.
        ktlint(libs.versions.ktlint.get())
            .editorConfigOverride(
                mapOf(
                    "ktlint_code_style" to "intellij_idea",
                    // Blank lines between short when branches are vertical noise here.
                    "ktlint_standard_blank-line-between-when-conditions" to "disabled",
                ),
            )
        // The project is AGPL; a missing header weakens the licence rather than merely
        // looking untidy, so it is enforced rather than trusted to reviewers.
        licenseHeaderFile(rootProject.file("config/spotless/license-header.txt"), "^(package|@file)")
    }

    kotlinGradle {
        target("**/*.gradle.kts")
        targetExclude("**/build/**")
        ktlint(libs.versions.ktlint.get())
            .editorConfigOverride(mapOf("ktlint_code_style" to "intellij_idea"))
    }

    format("misc") {
        target(
            "**/*.yml",
            "**/*.yaml",
            "**/*.json",
            "**/*.xml",
            "**/*.toml",
            ".gitignore",
            ".editorconfig",
            ".gitattributes",
        )
        targetExclude("**/build/**", "**/.gradle/**", "gradle/wrapper/**")
        trimTrailingWhitespace()
        endWithNewline()
    }

    format("markdown") {
        target("**/*.md")
        targetExclude("**/build/**")
        // No trailing-whitespace trimming here: in Markdown two trailing spaces are a
        // line break, and .editorconfig says the same.
        endWithNewline()
    }
}
