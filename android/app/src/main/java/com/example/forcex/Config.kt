package com.example.forcex

/**
 * Build-time baked configuration.
 *
 * FORCEX_URL and FORCEX_CLIENT_KEY are injected from environment variables by the
 * Gradle build script (app/build.gradle.kts). They must never be committed as
 * hard-coded values. In local development the Gradle defaults fall back to
 * http://10.0.2.2:5000 (the Android emulator's host loopback) and an empty key.
 *
 * In CI, the GitHub Actions workflow sets FORCEX_URL and FORCEX_CLIENT_KEY
 * from repository secrets before running ./gradlew assembleRelease.
 */
object Config {
    /** Base URL of the ForceX server (no trailing slash). */
    const val FORCEX_URL: String = BuildConfig.FORCEX_URL

    /** Shared secret presented on every request to pass the app-only gate. */
    const val CLIENT_KEY: String = BuildConfig.FORCEX_CLIENT_KEY

    /** Human-readable app version sent via X-ForceX-App-Version. */
    const val APP_VERSION: String = BuildConfig.VERSION_NAME

    /** Platform tag sent via X-ForceX-Platform. */
    const val PLATFORM: String = "android"
}
