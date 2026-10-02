plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
}

android {
    namespace = "com.example.forcex"
    compileSdk = 36

    defaultConfig {
        applicationId = "com.example.forcex"
        minSdk = 24
        targetSdk = 36
        versionCode = 1
        versionName = "1.0"

        // Bake FORCEX_URL and FORCEX_CLIENT_KEY from environment variables at build time.
        // CI sets these from repository secrets. Local dev falls back to the emulator loopback.
        val url = System.getenv("FORCEX_URL") ?: "http://10.0.2.2:5000"
        val key = System.getenv("FORCEX_CLIENT_KEY") ?: ""
        buildConfigField("String", "FORCEX_URL", "\"$url\"")
        buildConfigField("String", "FORCEX_CLIENT_KEY", "\"$key\"")
    }

    buildTypes {
        release {
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
        }
        debug {
            isMinifyEnabled = false
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    buildFeatures {
        buildConfig = true
        // Compose is not used — the app is a plain WebView Activity.
        compose = false
    }

    packaging {
        resources {
            excludes += "/META-INF/{AL2.0,LGPL2.1}"
        }
    }
}

kotlin {
    jvmToolchain(17)
}

dependencies {
    // Core Android — the only things the WebView Activity needs
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.activity)

    // Local unit tests
    testImplementation(libs.junit)

    // Instrumented tests
    androidTestImplementation(libs.androidx.test.core)
    androidTestImplementation(libs.androidx.test.ext.junit)
    androidTestImplementation(libs.androidx.test.runner)
    androidTestImplementation(libs.androidx.test.espresso.core)
}
