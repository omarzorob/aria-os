# Sideloading Aria OS UI on Android

This guide explains how to sideload the Aria OS Flutter APK onto a rooted Android device.

---

## Prerequisites

| Requirement | Version |
|---|---|
| Android device | Android 9+ (API 28+) |
| Root method | Magisk (recommended) or KernelSU |
| ADB | Platform-tools r34+ |
| USB Debugging | Enabled |

---

## Step 1: Enable Developer Options

1. Open **Settings → About phone**
2. Tap **Build number** 7 times
3. Go to **Settings → Developer options**
4. Enable:
   - **USB debugging** ✓
   - **Install via USB** ✓
   - **Disable permission monitoring** ✓ (optional, reduces dialogs)

---

## Step 2: Connect Your Device

```bash
# Connect via USB
adb devices

# You should see:
# List of devices attached
# ABC123DEF456   device

# If it shows "unauthorized", check your device for the authorization dialog
```

### ADB over WiFi (optional)
```bash
# Same network required
adb tcpip 5555
adb connect 192.168.1.X:5555
adb devices
```

---

## Step 3: Build the APK

```bash
# From the aria-os repo root:
./scripts/build_apk.sh release

# Output: dist/app-arm64-v8a-release.apk
```

> If you don't have Flutter installed, download a pre-built APK from
> [GitHub Releases](https://github.com/omarzorob/aria-os/releases).

---

## Step 4: Install the APK

```bash
# Standard install
adb install -r dist/app-arm64-v8a-release.apk

# If "INSTALL_FAILED_VERIFICATION_FAILURE":
adb install -r --bypass-low-target-sdk-block dist/app-arm64-v8a-release.apk

# Multi-ABI: install the matching architecture
# arm64-v8a = most modern phones
# armeabi-v7a = older 32-bit phones
# x86_64 = emulators

# Check your device arch:
adb shell getprop ro.product.cpu.abi
```

---

## Step 5: Grant Required Permissions

Aria OS needs several permissions to function as your AI assistant:

```bash
PACKAGE="com.aria.ui"

# Microphone (voice mode)
adb shell pm grant $PACKAGE android.permission.RECORD_AUDIO

# Notifications (notification access)
adb shell cmd notification allow_listener $PACKAGE/com.aria.NotificationListener

# Accessibility service
adb shell settings put secure enabled_accessibility_services \
  "$PACKAGE/com.aria.AriaAccessibilityService"

# SMS access (requires Aria as default SMS app or grant)
adb shell pm grant $PACKAGE android.permission.READ_SMS
adb shell pm grant $PACKAGE android.permission.SEND_SMS

# Contacts
adb shell pm grant $PACKAGE android.permission.READ_CONTACTS
adb shell pm grant $PACKAGE android.permission.WRITE_CONTACTS

# Calendar
adb shell pm grant $PACKAGE android.permission.READ_CALENDAR
adb shell pm grant $PACKAGE android.permission.WRITE_CALENDAR

# Call log
adb shell pm grant $PACKAGE android.permission.READ_CALL_LOG
adb shell pm grant $PACKAGE android.permission.WRITE_CALL_LOG

# Phone (dialing)
adb shell pm grant $PACKAGE android.permission.CALL_PHONE

# Storage (screenshots, files)
adb shell pm grant $PACKAGE android.permission.READ_EXTERNAL_STORAGE
adb shell pm grant $PACKAGE android.permission.WRITE_EXTERNAL_STORAGE
```

---

## Step 6: Start the Aria Agent

The Flutter UI connects to the Aria Python agent running on port 8765.
Start it from the aria-os repo on your computer or Termux:

```bash
# On your computer (connected via ADB):
cd aria-os
python main.py --serve --port 8765

# Port-forward so the Android app can reach it:
adb reverse tcp:8765 tcp:8765

# Now the Android app at localhost:8765 will tunnel to your machine
```

### Running Aria directly on device (Termux, advanced)
```bash
# Install Termux from F-Droid
# Inside Termux:
pkg install python git
git clone https://github.com/omarzorob/aria-os
cd aria-os
pip install -r requirements.txt
python main.py --serve --port 8765
```

---

## Step 7: Launch Aria UI

```bash
adb shell am start -n com.aria.ui/.MainActivity
```

Or tap the **Aria** app icon in your launcher.

---

## Rooted Device — Extra Setup

On a rooted device, you can grant additional elevated permissions:

```bash
# Allow ADB shell to run as root (Magisk)
adb root

# Install the Aria Accessibility Service APK
adb install -r aria-accessibility-service.apk

# Enable system-level notification listener without confirmation dialog
adb shell settings put secure enabled_notification_listeners \
  "com.aria.ui/com.aria.NotificationListener:com.aria.accessibilityservice/.AriaNotificationService"
```

---

## Troubleshooting

| Problem | Solution |
|---|---|
| `INSTALL_FAILED_VERIFICATION_FAILURE` | Settings → Security → Unknown sources → Enable |
| App crashes on launch | `adb logcat -s flutter` to see Dart errors |
| Agent not connecting | Run `adb reverse tcp:8765 tcp:8765`, ensure agent is running |
| Permissions denied | Re-run grant commands above as root |
| ADB not found | Install [Android SDK Platform Tools](https://developer.android.com/tools/releases/platform-tools) |
| Voice not working | Grant RECORD_AUDIO; check mic permissions in app settings |

---

## Useful ADB Commands

```bash
# View Aria logs
adb logcat -s "Aria" "flutter"

# Screenshot
adb exec-out screencap -p > screen.png

# Check if agent is reachable from device
adb shell curl -s http://localhost:8765/health

# Uninstall
adb uninstall com.aria.ui

# Clear app data (reset)
adb shell pm clear com.aria.ui
```

---

## Architecture Notes

```
Your Computer / Server
    ↓ ADB reverse tunnel (tcp:8765)
Android Device
    ↓ HTTP localhost:8765
Aria Flutter UI  ←→  Aria Python Agent
                          ↓ ADB
                      Android OS (SMS, Calls, etc.)
```

The Flutter UI is just the chat interface. The intelligence lives in the Python agent.

---

*Built with ❤️ for Aria OS — the AI-native Android OS*
