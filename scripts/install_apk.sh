#!/usr/bin/env bash
# ============================================================
# scripts/install_apk.sh
# Installs the Aria OS APK on a connected Android device
#
# Usage:
#   ./scripts/install_apk.sh [device-serial] [release|debug]
#
# Examples:
#   ./scripts/install_apk.sh               # installs on first device
#   ./scripts/install_apk.sh ABC123 debug  # specific device, debug build
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
DIST_DIR="$REPO_ROOT/dist"

DEVICE_SERIAL="${1:-}"
BUILD_TYPE="${2:-release}"
PACKAGE="com.aria.ui"
PORT="${ARIA_PORT:-8765}"

RED='\033[0;31m'; GREEN='\033[0;32m'; BLUE='\033[0;34m'; NC='\033[0m'
info()    { echo -e "${BLUE}[aria-install]${NC} $*"; }
success() { echo -e "${GREEN}[aria-install]${NC} ✓ $*"; }
error()   { echo -e "${RED}[aria-install]${NC} ✗ $*" >&2; exit 1; }

ADB_CMD="adb"
[[ -n "$DEVICE_SERIAL" ]] && ADB_CMD="adb -s $DEVICE_SERIAL"

# Check device
info "Checking device connection..."
if ! $ADB_CMD get-state &>/dev/null; then
  error "No device connected. Run 'adb devices' to check."
fi

DEVICE_MODEL=$($ADB_CMD shell getprop ro.product.model 2>/dev/null || echo "Unknown")
DEVICE_ARCH=$($ADB_CMD shell getprop ro.product.cpu.abi 2>/dev/null || echo "arm64-v8a")
ANDROID_VER=$($ADB_CMD shell getprop ro.build.version.release 2>/dev/null || echo "?")

info "Device: $DEVICE_MODEL (Android $ANDROID_VER, $DEVICE_ARCH)"

# Find APK
APK_PATH=""
for arch in "$DEVICE_ARCH" "arm64-v8a" "armeabi-v7a" "universal"; do
  candidate="$DIST_DIR/app-$arch-$BUILD_TYPE.apk"
  if [[ -f "$candidate" ]]; then
    APK_PATH="$candidate"
    break
  fi
done

# Fallback: look for any APK in dist
if [[ -z "$APK_PATH" ]]; then
  APK_PATH=$(ls "$DIST_DIR"/*.apk 2>/dev/null | head -1 || true)
fi

if [[ -z "$APK_PATH" ]]; then
  error "No APK found in $DIST_DIR/. Run ./scripts/build_apk.sh first."
fi

info "Installing: $(basename "$APK_PATH")"
$ADB_CMD install -r "$APK_PATH"
success "APK installed"

# Set up port forward
info "Setting up ADB reverse port forward (localhost:$PORT)..."
$ADB_CMD reverse tcp:$PORT tcp:$PORT
success "Port $PORT forwarded device → host"

# Launch the app
info "Launching Aria UI..."
$ADB_CMD shell am start -n "$PACKAGE/.MainActivity" 2>/dev/null || true
success "Aria UI launched"

echo ""
echo "  Aria is running! Start the agent on your computer:"
echo "  cd aria-os && python main.py --serve --port $PORT"
echo ""
