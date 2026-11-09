import java.util.Properties

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

// Release signing, only if android/keystore.properties exists (storeFile, storePassword, keyAlias, keyPassword).
val keystore = Properties().apply {
    rootProject.file("keystore.properties").takeIf { it.exists() }?.inputStream()?.use { load(it) }
}

android {
    namespace = "io.github.greenwichdelazaren.stickman"
    compileSdk = 36

    defaultConfig {
        applicationId = "io.github.greenwichdelazaren.stickman"
        minSdk = 26
        targetSdk = 36
        versionCode = 1
        versionName = findProperty("stickmanVersion") as String? ?: "1.0"  // android/build.py: scene.VERSION
    }

    signingConfigs {
        if (!keystore.isEmpty) {
            create("release") {
                storeFile = rootProject.file(keystore.getProperty("storeFile"))
                storePassword = keystore.getProperty("storePassword")
                keyAlias = keystore.getProperty("keyAlias")
                keyPassword = keystore.getProperty("keyPassword")
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            signingConfig = signingConfigs.findByName("release")
        }
    }

    buildFeatures {
        buildConfig = true
    }

    // Made by android/build.py: the website with its libraries, and the launcher icons.
    sourceSets["main"].assets.srcDir("../generated/assets")
    sourceSets["main"].res.srcDir("../generated/res")

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
}

dependencies {
    implementation("androidx.activity:activity-ktx:1.10.1")
    implementation("androidx.core:core-ktx:1.16.0")
    implementation("androidx.webkit:webkit:1.14.0")
}
