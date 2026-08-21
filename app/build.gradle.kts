plugins {
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
        versionCode = 1
        versionName = "0.1.0-m0"
    }

    buildFeatures {
        buildConfig = true
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
}
