# Aria OS — Setup Guide

## Prerequisites

| Tool | Version | Notes |
|------|---------|-------|
| Android Studio | Hedgehog+ | For editing + SDK management |
| Flutter SDK | 3.16+ | `flutter --version` |
| Android SDK | API 28–34 | Install via Android Studio SDK Manager |
| Java / JDK | 17 | Set `JAVA_HOME` |
| ADB | Any | Usually bundled with Android Studio |
| Android Phone | Android 9+ | API 28 minimum; rooted preferred |

---

## Step 1: Install Flutter

```bash
# Download Flutter SDK
git clone https://github.com/flutter/flutter.git -b stable ~/flutter
export PATH="$PATH:$HOME/flutter/bin"

# Verify
flutter doctor
```

All checks should pass (ignore the Xcode check if not on macOS).

---

## Step 2: Set Up Android SDK

In Android Studio:
1. **SDK Manager** → Install **Android 14 (API 34)**
2. Install **Android Build Tools 34.0.0**
3. Install **Android NDK** (optional, for future JNI)

Set in your shell profile:
```bash
export ANDROID_HOME="$HOME/Android/Sdk"
export PATH="$PATH:$ANDROID_HOME/platform-tools:$ANDROID_HOME/tools"
```

---

## Step 3: Configure API Key

The Claude API key is stored in the app's `SharedPreferences` at runtime — **not** hardcoded in source.

**Option A — via the app:**
1. Install the APK (step 5)
2. Open Aria → Settings → Enter API Key → Save

**Option B — via build config (advanced):**
Create `aria-app/android/local.properties`:
```
sdk.dir=/home/you/Android/Sdk
CLAUDE_API_KEY=sk-ant-...
```
Then in `app/build.gradle` defaultConfig:
```groovy
buildConfigField "String", "CLAUDE_API_KEY", "\"${localProperties['CLAUDE_API_KEY'] ?: ''}\""
```

---

## Step 4: Build the APK

```bash
cd /path/to/aria-os

# Quick build (uses the script)
bash scripts/build.sh

# Manual build
cd aria-app
flutter pub get
flutter build apk --debug

# Release build (requires signing config)
flutter build apk --release
```

Output: `aria-app/build/app/outputs/flutter-apk/app-debug.apk`

---

## Step 5: Install on Phone

**Enable developer options on phone:**
Settings → About Phone → tap Build Number 7 times → Developer Options → Enable USB debugging

**Install via ADB:**
```bash
adb devices          # verify phone is connected
adb install -r aria-app/build/app/outputs/flutter-apk/app-debug.apk
```

Or use the script:
```bash
bash scripts/install.sh
```

---

## Step 6: Enable Accessibility Service

This is **required** for Aria to read screen content and perform gestures.

1. On your Android phone: **Settings → Accessibility**
2. Scroll to **Downloaded Apps** or **Installed Services**
3. Tap **Aria** → Toggle ON
4. Confirm the warning prompt

> ⚠️ The accessibility service allows Aria to read and interact with any app on your screen. This is intentional — it's how Aria operates as a true AI OS layer.

---

## Step 7: Grant Permissions

On first launch, Aria will request:
- Microphone (voice input)
- Contacts (read/write)
- Phone (make calls)
- SMS (send/receive)
- Calendar (read/write)
- Notifications (read active notifications)

Grant all of them for full functionality.

---

## Step 8: Test It

1. Open Aria → Chat screen
2. Type: "What's the weather in Chicago?"
3. Aria should respond with current weather (Open-Meteo API, no key needed)
4. Type: "Send a test SMS to [a contact name]"
5. Aria should look up the contact and send the SMS

---

## Troubleshooting

### "Aria service not starting"
- Check that the app has been launched at least once
- On some OEMs (Xiaomi, Samsung), auto-start must be explicitly allowed:
  Settings → Battery → App Launch → Aria → Manual → enable all three

### "Accessibility service keeps getting disabled"
- Some phones (MIUI, OneUI) aggressively disable accessibility services
- Root + Magisk: use a Magisk module to protect the service
- Alternative: add Aria to the "device admin" list

### "Voice recognition not working"
- Ensure microphone permission is granted
- Ensure Google app or a speech recognition service is installed
- Test: Settings → Language & Input → Voice Input → Default

### "Build fails: Flutter SDK not found"
- Ensure `flutter` is in `PATH`
- Run `flutter doctor` and fix all red items

### "kapt annotation processing fails"
- Ensure JDK 17 is active: `java -version`
- In Android Studio: File → Project Structure → SDK Location → JDK location

### "API calls fail with 401"
- Check API key is correctly entered in Settings
- Ensure no extra spaces or newlines in the key field
- Verify key is active at console.anthropic.com

---

## Development Workflow

```bash
# Run on connected device (hot reload)
cd aria-app
flutter run

# Watch for Kotlin compile errors
cd aria-app/android
./gradlew compileDebugKotlin

# Run unit tests
./gradlew test

# Clean build
flutter clean && flutter pub get && flutter build apk --debug
```

---

## Building for Release

1. Generate a signing keystore:
```bash
keytool -genkey -v -keystore aria-release.jks -keyalg RSA -keysize 2048 -validity 10000 -alias aria
```

2. Create `aria-app/android/key.properties`:
```
storePassword=<password>
keyPassword=<password>
keyAlias=aria
storeFile=../aria-release.jks
```

3. Build:
```bash
flutter build apk --release
```
