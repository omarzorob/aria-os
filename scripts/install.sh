#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
APK="$REPO_ROOT/aria-app/build/app/outputs/flutter-apk/app-debug.apk"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Aria OS Install Script"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Verify ADB is installed
if ! command -v adb &> /dev/null; then
    echo "❌ ADB not found in PATH"
    echo "   Install Android SDK platform-tools"
    exit 1
fi

# Verify APK exists
if [ ! -f "$APK" ]; then
    echo "❌ APK not found: $APK"
    echo "   Run: bash scripts/build.sh first"
    exit 1
fi

# Verify device is connected
DEVICES=$(adb devices | grep -v "List of devices" | grep "device$" | wc -l)
if [ "$DEVICES" -eq 0 ]; then
    echo "❌ No Android device connected"
    echo "   Connect phone via USB and enable USB debugging"
    adb devices
    exit 1
fi

echo "📱 Connected device:"
adb devices | grep "device$" | head -1

echo ""
echo "📲 Installing Aria..."
adb install -r "$APK"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ✅ Aria installed successfully!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  Next steps:"
echo "  1. Open Aria on your phone"
echo "  2. Go to Settings → Enter your Claude API key"
echo "  3. Go to Android Settings → Accessibility → Aria → Enable"
echo "  4. Say 'Hey Aria' or tap the app to start"
echo ""

# Optionally launch the app
echo "  Launching Aria..."
adb shell am start -n "ai.aria.os.debug/ai.aria.os.MainActivity" 2>/dev/null || \
adb shell am start -n "ai.aria.os/ai.aria.os.MainActivity" 2>/dev/null || \
echo "  (Open Aria manually from your launcher)"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
