#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
APP_DIR="$REPO_ROOT/aria-app"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Aria OS Build Script"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Verify Flutter is installed
if ! command -v flutter &> /dev/null; then
    echo "❌ Flutter not found in PATH"
    echo "   Install Flutter: https://docs.flutter.dev/get-started/install"
    exit 1
fi

echo "Flutter version: $(flutter --version | head -1)"
echo ""

cd "$APP_DIR"

echo "📦 Installing dependencies..."
flutter pub get

echo ""
echo "🔨 Building debug APK..."
flutter build apk --debug

APK_PATH="$APP_DIR/build/app/outputs/flutter-apk/app-debug.apk"

if [ -f "$APK_PATH" ]; then
    APK_SIZE=$(du -sh "$APK_PATH" | cut -f1)
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  ✅ Build successful!"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  APK: $APK_PATH"
    echo "  Size: $APK_SIZE"
    echo ""
    echo "  Install: bash scripts/install.sh"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
else
    echo "❌ Build failed — APK not found"
    exit 1
fi
