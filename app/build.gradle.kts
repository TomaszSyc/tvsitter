/*
 * TV Sitter — parental control for Android TV / Google TV.
 * Copyright (C) 2026 Tomasz Syc
 * SPDX-License-Identifier: AGPL-3.0-only
 */
// One version for the whole product (D6), read from version.txt rather than written here
// twice. The two halves had already drifted — the app said 0.1.0-m0 while the integration
// said 0.1.0 — and nothing noticed, which also meant the `fw` field in every state payload
// could not identify a build, though that is the only reason it exists.
val productVersion: String = providers
    .fileContents(rootProject.layout.projectDirectory.file("version.txt"))
    .asText
    .get()
    .trim()

plugins {
    alias(libs.plugins.detekt)
    // AGP 9+ ships built-in Kotlin support; the separate kotlin-android plugin is not
    // just redundant, it is actively rejected.
    alias(libs.plugins.android.application)
}

android {
    namespace = "app.tvsitter.tv"
    compileSdk = 37

    defaultConfig {
        applicationId = "app.tvsitter.tv"
        // minSdk 26 = Android 8: java.time without desugaring, and no realistic
        // Google TV / Android TV device is older anyway.
        minSdk = 26
        targetSdk = 37
        // Derived, so releasing does not depend on remembering to bump a second number.
        // Monotonic while minor and patch stay under a hundred, which for this project they
        // will.
        versionCode = productVersion.split(".").let { (major, minor, patch) ->
            major.toInt() * 10_000 + minor.toInt() * 100 + patch.toInt()
        }
        versionName = productVersion
    }

    buildFeatures {
        buildConfig = true
    }

    packaging {
        resources {
            // The HiveMQ client pulls in six Netty jars, each carrying these. INDEX.LIST is
            // a jar index and io.netty.versions.properties is build metadata; neither means
            // anything inside an APK, so dropping them loses nothing.
            excludes += setOf(
                "META-INF/INDEX.LIST",
                "META-INF/io.netty.versions.properties",
                "META-INF/DEPENDENCIES",
            )
            // Licence and notice files are kept rather than excluded — Netty is Apache-2.0
            // and its NOTICE has to travel with the binary. pickFirst keeps one copy where
            // the plain merge refuses duplicates. Proper third-party attribution before a
            // public release is tracked separately; see the going-public checklist.
            pickFirsts += setOf(
                "META-INF/LICENSE",
                "META-INF/LICENSE.txt",
                "META-INF/NOTICE",
                "META-INF/NOTICE.txt",
            )
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}

kotlin {
    compilerOptions {
        jvmTarget.set(org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17)
    }
}

dependencies {
    implementation(project(":rules"))
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.annotation)
    // For OnBackPressedDispatcher: lint refuses both onBackPressed and intercepting the key,
    // and it is right that callbacks are the current answer even on a set with no gestures.
    implementation(libs.androidx.activity)
    implementation(libs.androidx.datastore.preferences)
    implementation(libs.kotlinx.coroutines.android)
    implementation(libs.kotlinx.serialization.json)
    implementation(libs.hivemq.mqtt.client)
}

detekt {
    buildUponDefaultConfig = true
    config.setFrom(rootProject.file("config/detekt/detekt.yml"))
}
