#!/usr/bin/env bash
# ============================================================
# scripts/build_apk.sh
# Builds the Aria OS Flutter UI APK for Android
#
# Usage:
#   ./scripts/build_apk.sh [release|debug|profile]
#
# Output: apps/aria_ui/build/app/outputs/flutter-apk/
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
UI_DIR="$REPO_ROOT/apps/aria_ui"
BUILD_TYPE="${1:-release}"
APK_OUTPUT_DIR="$UI_DIR/build/app/outputs/flutter-apk"
DIST_DIR="$REPO_ROOT/dist"

# ---- Color helpers ----
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

info()    { echo -e "${BLUE}[aria-build]${NC} $*"; }
success() { echo -e "${GREEN}[aria-build]${NC} ✓ $*"; }
warn()    { echo -e "${YELLOW}[aria-build]${NC} ⚠ $*"; }
error()   { echo -e "${RED}[aria-build]${NC} ✗ $*" >&2; }

# ---- Validate Flutter installation ----
if ! command -v flutter &>/dev/null; then
  error "Flutter not found. Install from https://docs.flutter.dev/get-started/install"
  exit 1
fi

FLUTTER_VERSION=$(flutter --version 2>&1 | head -1)
info "Flutter: $FLUTTER_VERSION"

# ---- Validate build type ----
case "$BUILD_TYPE" in
  release|debug|profile) ;;
  *)
    error "Invalid build type: $BUILD_TYPE (use: release | debug | profile)"
    exit 1
    ;;
esac

info "Build type: $BUILD_TYPE"
info "Project: $UI_DIR"
echo ""

# ---- Navigate to Flutter project ----
cd "$UI_DIR"

# ---- Create asset directories if missing ----
mkdir -p assets/icons assets/images

# ---- Get Flutter dependencies ----
info "Fetching Flutter dependencies..."
flutter pub get

# ---- Run linter ----
info "Running Dart analyzer..."
flutter analyze --no-fatal-infos || warn "Analyzer warnings present (non-fatal)"

# ---- Build APK ----
info "Building APK ($BUILD_TYPE)..."

if [[ "$BUILD_TYPE" == "release" ]]; then
  # Release build — requires keystore for signing
  if [[ -n "${KEYSTORE_PATH:-}" && -f "$KEYSTORE_PATH" ]]; then
    info "Signing with keystore: $KEYSTORE_PATH"
    flutter build apk \
      --release \
      --obfuscate \
      --split-debug-info="$DIST_DIR/debug-info" \
      --split-per-abi
  else
    warn "No keystore configured — building unsigned release APK"
    warn "Set KEYSTORE_PATH, KEYSTORE_PASS, KEY_ALIAS, KEY_PASS env vars for signing"
    flutter build apk --release --split-per-abi
  fi
elif [[ "$BUILD_TYPE" == "debug" ]]; then
  flutter build apk --debug
else
  flutter build apk --profile
fi

# ---- Copy to dist/ ----
mkdir -p "$DIST_DIR"
APK_FILES=("$APK_OUTPUT_DIR"/*.apk)

if [[ ${#APK_FILES[@]} -eq 0 || ! -f "${APK_FILES[0]}" ]]; then
  error "Build succeeded but no APK found in $APK_OUTPUT_DIR"
  exit 1
fi

info "APKs built:"
for apk in "${APK_FILES[@]}"; do
  size=$(du -sh "$apk" | cut -f1)
  apk_name=$(basename "$apk")
  cp "$apk" "$DIST_DIR/$apk_name"
  success "$apk_name ($size) → dist/$apk_name"
done

echo ""
success "Build complete! APKs in: $DIST_DIR/"
echo ""
echo "Next steps:"
echo "  1. Connect Android device: adb devices"
echo "  2. Install: adb install -r dist/app-arm64-v8a-$BUILD_TYPE.apk"
echo "  3. Launch: adb shell am start -n com.aria.ui/.MainActivity"
echo ""
echo "Or run: ./scripts/install_apk.sh [device-serial]"
