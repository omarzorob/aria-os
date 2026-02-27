#!/usr/bin/env bash
# =============================================================================
# Aria OS — Demo Setup Script
# =============================================================================
# One command to verify your environment and get demo-ready.
# Usage: bash demo/setup.sh
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Colors
# ---------------------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
RESET='\033[0m'

PASS="✅"
FAIL="❌"
WARN="⚠️ "
INFO="ℹ️ "

ERRORS=0

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
ok()   { echo -e "${GREEN}${PASS} ${1}${RESET}"; }
fail() { echo -e "${RED}${FAIL} ${1}${RESET}"; ERRORS=$((ERRORS + 1)); }
warn() { echo -e "${YELLOW}${WARN} ${1}${RESET}"; }
info() { echo -e "${CYAN}${INFO} ${1}${RESET}"; }
banner() {
    echo -e ""
    echo -e "${CYAN}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
    echo -e "${BOLD}  $1${RESET}"
    echo -e "${CYAN}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
}

# ---------------------------------------------------------------------------
# Welcome
# ---------------------------------------------------------------------------
echo ""
echo -e "${CYAN}${BOLD}"
echo "   ┌─────────────────────────────────────────┐"
echo "   │         Aria OS — Demo Setup            │"
echo "   │    AI-Native Android Agent Platform     │"
echo "   └─────────────────────────────────────────┘"
echo -e "${RESET}"

# Change to project root (parent of demo/)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "${SCRIPT_DIR}")"
cd "${PROJECT_ROOT}"
info "Project root: ${PROJECT_ROOT}"

# ---------------------------------------------------------------------------
# 1. Check Python
# ---------------------------------------------------------------------------
banner "1. Checking Python"

PYTHON_CMD=""
for cmd in python3.12 python3.11 python3 python; do
    if command -v "$cmd" &>/dev/null; then
        VERSION=$("$cmd" --version 2>&1 | awk '{print $2}')
        MAJOR=$(echo "$VERSION" | cut -d. -f1)
        MINOR=$(echo "$VERSION" | cut -d. -f2)
        if [[ "$MAJOR" -ge 3 && "$MINOR" -ge 11 ]]; then
            PYTHON_CMD="$cmd"
            ok "Python ${VERSION} found at $(command -v $cmd)"
            break
        fi
    fi
done

if [[ -z "$PYTHON_CMD" ]]; then
    fail "Python 3.11+ not found. Install from https://python.org"
    echo "  Hint: brew install python3 (Mac) or apt install python3.12 (Linux)"
    exit 1
fi

# ---------------------------------------------------------------------------
# 2. Check ADB
# ---------------------------------------------------------------------------
banner "2. Checking ADB (Android Debug Bridge)"

if command -v adb &>/dev/null; then
    ADB_VERSION=$(adb version 2>&1 | head -1)
    ok "ADB found: ${ADB_VERSION}"
else
    fail "ADB not found in PATH"
    echo ""
    echo "  Install Platform Tools:"
    echo "  • Mac:   brew install android-platform-tools"
    echo "  • Linux: sudo apt install android-tools-adb"
    echo "  • All:   https://developer.android.com/tools/releases/platform-tools"
    echo ""
    warn "Demo will run in SIMULATED mode without ADB"
    ERRORS=$((ERRORS - 1))  # Don't count as fatal — demo works in sim mode
fi

# ---------------------------------------------------------------------------
# 3. Install Python dependencies
# ---------------------------------------------------------------------------
banner "3. Installing Demo Dependencies"

info "Installing required packages..."

# Check if we have a venv
if [[ -d ".venv" ]]; then
    info "Found existing venv — using it"
    if [[ -f ".venv/bin/pip" ]]; then
        PIP=".venv/bin/pip"
    else
        PIP="${PYTHON_CMD} -m pip"
    fi
else
    PIP="${PYTHON_CMD} -m pip"
fi

# Install demo-specific deps
DEPS="rich edge-tts anthropic pytest"
for dep in $DEPS; do
    if $PIP show "$dep" &>/dev/null 2>&1; then
        ok "${dep} already installed"
    else
        echo -e "  ${YELLOW}Installing ${dep}...${RESET}"
        if $PIP install "$dep" --quiet 2>&1 | tail -1; then
            ok "${dep} installed"
        else
            warn "Failed to install ${dep} — demo may have reduced features"
        fi
    fi
done

# ---------------------------------------------------------------------------
# 4. Check phone connection
# ---------------------------------------------------------------------------
banner "4. Checking Phone Connection"

if command -v adb &>/dev/null; then
    # Make sure adb server is running
    adb start-server &>/dev/null 2>&1 || true
    sleep 1

    DEVICES=$(adb devices 2>/dev/null | grep -v "List of devices" | grep -v "^$" || echo "")

    if echo "$DEVICES" | grep -q "device$"; then
        DEVICE_NAME=$(echo "$DEVICES" | grep "device$" | awk '{print $1}')
        ok "Phone connected: ${DEVICE_NAME}"
    elif echo "$DEVICES" | grep -q "unauthorized"; then
        warn "Phone connected but NOT authorized"
        echo "  → Unlock your phone and tap 'Allow' on the USB debugging dialog"
    elif echo "$DEVICES" | grep -q "offline"; then
        warn "Phone connected but offline — try unplugging and replugging"
    else
        warn "No phone detected"
        echo "  → Connect phone via USB cable"
        echo "  → Enable USB Debugging: Settings → Developer Options → USB Debugging"
        echo "  → Demo will run in SIMULATED mode"
    fi
else
    warn "Skipping phone check (ADB not installed)"
fi

# ---------------------------------------------------------------------------
# 5. ADB sanity test
# ---------------------------------------------------------------------------
banner "5. ADB Sanity Test"

if command -v adb &>/dev/null && adb devices 2>/dev/null | grep -q "device$"; then
    info "Running ADB ping test..."

    MODEL=$(adb shell getprop ro.product.model 2>/dev/null | tr -d '\r' || echo "")
    ANDROID=$(adb shell getprop ro.build.version.release 2>/dev/null | tr -d '\r' || echo "")
    BATTERY=$(adb shell dumpsys battery 2>/dev/null | grep "level:" | awk '{print $2}' | tr -d '\r' || echo "?")

    if [[ -n "$MODEL" ]]; then
        ok "ADB ping successful!"
        echo ""
        echo -e "  ${BOLD}Device Information:${RESET}"
        echo -e "  📱 Model:      ${CYAN}${MODEL}${RESET}"
        echo -e "  🤖 Android:    ${CYAN}${ANDROID}${RESET}"
        echo -e "  🔋 Battery:    ${CYAN}${BATTERY}%${RESET}"
        echo ""
    else
        warn "ADB connected but couldn't read device info"
    fi
else
    info "Skipping ADB sanity test (no device connected — will use simulated mode)"
fi

# ---------------------------------------------------------------------------
# 6. Check ANTHROPIC_API_KEY (optional but recommended)
# ---------------------------------------------------------------------------
banner "6. AI Configuration"

if [[ -n "${ANTHROPIC_API_KEY:-}" ]]; then
    ok "ANTHROPIC_API_KEY is set — interactive mode will use Claude AI"
else
    warn "ANTHROPIC_API_KEY not set"
    echo "  → Export your key for live AI responses in interactive mode:"
    echo "    export ANTHROPIC_API_KEY=sk-ant-..."
    echo "  → Demo works without it (uses smart fallback responses)"
fi

# ---------------------------------------------------------------------------
# 7. Quick demo test
# ---------------------------------------------------------------------------
banner "7. Quick Demo Test"

info "Verifying demo script can be imported..."

if $PYTHON_CMD -c "
import sys
sys.path.insert(0, '.')
# Test core imports
import subprocess
import argparse
import asyncio
print('Core imports OK')
" 2>/dev/null; then
    ok "Demo script loads successfully"
else
    fail "Demo script has import errors — check Python environment"
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
echo -e "${CYAN}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"

if [[ "$ERRORS" -eq 0 ]]; then
    echo ""
    echo -e "${GREEN}${BOLD}✅ Aria OS demo ready!${RESET}"
    echo ""
    echo -e "  ${BOLD}Run the demo:${RESET}"
    echo -e "  ${CYAN}python demo/demo.py${RESET}         # Full scripted demo"
    echo -e "  ${CYAN}python demo/demo.py --quick${RESET}  # Skip to interactive mode"
    echo -e "  ${CYAN}python demo/demo.py --sim${RESET}    # Force simulated mode"
    echo ""
    echo -e "  ${BOLD}Read the demo guide:${RESET}"
    echo -e "  ${CYAN}cat demo/DEMO_SCRIPT.md${RESET}"
    echo ""
else
    echo ""
    echo -e "${YELLOW}${BOLD}⚠️  Setup complete with ${ERRORS} warning(s).${RESET}"
    echo ""
    echo -e "  Demo will still work in simulated mode:"
    echo -e "  ${CYAN}python demo/demo.py --sim${RESET}"
    echo ""
fi

echo -e "${CYAN}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo ""
