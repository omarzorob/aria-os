# 📱 Aria OS — Demo Setup Guide

> Get from zero to live demo in under 5 minutes.

---

## Prerequisites

| Requirement | Version | Check |
|-------------|---------|-------|
| Python | 3.11+ | `python3 --version` |
| pip | latest | `pip --version` |
| ADB | any | `adb version` |
| Android phone | Android 8.0+ | — |
| USB cable | data cable (not charge-only) | — |

### Install ADB

**macOS:**
```bash
brew install android-platform-tools
```

**Ubuntu / Debian:**
```bash
sudo apt update && sudo apt install android-tools-adb
```

**Windows:**
Download from [Android Platform Tools](https://developer.android.com/tools/releases/platform-tools) and add to PATH.

**Verify:**
```bash
adb version
# Android Debug Bridge version 1.0.41
```

---

## Enable USB Debugging on your phone

1. Go to **Settings → About phone**
2. Tap **Build number** 7 times (you'll see "You are now a developer!")
3. Go to **Settings → Developer options**
4. Enable **USB debugging**
5. Plug in your phone via USB
6. On your phone, tap **"Allow"** on the authorization dialog

**Verify:**
```bash
adb devices
# List of devices attached
# ABC123XYZ    device   ← your phone
```

If you see `unauthorized` instead of `device` → unlock your phone and tap Allow.

---

## Setup Steps

### 1. Clone the repo
```bash
git clone https://github.com/yourusername/aria-os.git
cd aria-os
```

### 2. Run the automated setup
```bash
bash demo/setup.sh
```

This will:
- ✅ Check Python version
- ✅ Check ADB installation
- ✅ Install demo dependencies (rich, edge-tts, anthropic)
- ✅ Verify phone connection
- ✅ Run a quick ADB ping test

### 3. (Optional) Set your AI API key for live responses
```bash
export ANTHROPIC_API_KEY=sk-ant-your-key-here
```

Without this, Aria uses smart fallback responses in interactive mode. The demo still looks great.

### 4. Run the demo
```bash
python demo/demo.py
```

---

## Demo Modes

### Full scripted demo (default)
```bash
python demo/demo.py
```
Runs the full 10-step showcase, then enters interactive mode.

### Quick interactive mode
```bash
python demo/demo.py --quick
```
Skips the scripted steps. Great for when you want to jump straight to "what can it do?"

### Simulated mode (no phone needed)
```bash
python demo/demo.py --sim
```
All demo steps run with realistic simulated data. Perfect for rehearsing.

---

## What the Demo Looks Like

```
╔═══════════════════════════════════════════════════════╗
║                                                       ║
║        ██████╗      █████╗     ██████╗     ██████╗   ║
║       ██╔════╝     ██╔══██╗    ██╔══██╗    ██╔══██╗  ║
║       ██║  ███╗    ███████║    ██████╔╝    ██████╔╝  ║
║       ██║   ██║    ██╔══██║    ██╔══██╗    ██╔══██╗  ║
║       ╚██████╔╝    ██║  ██║    ██║  ██║    ██████╔╝  ║
║        ╚═════╝     ╚═╝  ╚═╝    ╚═╝  ╚═╝    ╚═════╝   ║
║                                                       ║
║            AI-Native Android Agent Platform           ║
║                    LIVE DEMO v1.0                     ║
╚═══════════════════════════════════════════════════════╝

           The AI that lives inside your phone.

━━━━━━━━━━━━━━ Step 1: Connecting to Android Device ━━━━━━━━━━━━━━

  ▶ Running: adb devices
  ⠋ Scanning for connected devices...
  ✓ Device connected and authorized!

━━━━━━━━━━━━━━ Step 2: Reading Device Information ━━━━━━━━━━━━━━

  ▶ Fetching device properties via ADB...

  ╭──────────────────────────────────╮
  │ 📱 Manufacturer  Google          │
  │ 📱 Model         Pixel 8 Pro     │
  │ 🤖 Android       14              │
  │ 🔧 SDK Version   34              │
  │ 🔋 Battery       87%             │
  ╰──────────────────────────────────╯

  ╭─────────────────── 🤖 Aria ──────────────────╮
  │ Connected to your Google Pixel 8 Pro running │
  │ Android 14. Battery is at 87 percent.        │
  ╰──────────────────────────────────────────────╯

...

━━━━━━━━━━━━━ 🎤 Interactive Mode ━━━━━━━━━━━━━━

  ╭─────────── 🤖 Aria — Interactive Mode ────────────╮
  │ Aria is now listening.                             │
  │ Type your command and press Enter.                 │
  │                                                    │
  │ Examples:                                          │
  │ • Send a text to Mom saying I'll be home by 7     │
  │ • What's on my calendar today?                    │
  │ • Set a reminder to call the office at 2pm        │
  │ • Open Spotify and play something relaxing        │
  ╰────────────────────────────────────────────────────╯

You: Send a text to Mom saying I'm on my way

  ⠋ Aria is thinking...

  ╭─────────── 🤖 Aria ───────────╮
  │ Sending that text to Mom now. │
  │ Opening SMS... message sent!  │
  ╰───────────────────────────────╯
```

---

## Running the Tests

```bash
python -m pytest tests/test_demo_flow.py -v
```

Expected output:
```
tests/test_demo_flow.py::TestADBBridgeCore::test_run_command_builds_correct_args PASSED
tests/test_demo_flow.py::TestADBBridgeCore::test_run_command_with_serial PASSED
tests/test_demo_flow.py::TestADBBridgeCore::test_run_command_raises_on_error PASSED
tests/test_demo_flow.py::TestADBBridgeCore::test_run_command_raises_when_adb_missing PASSED
tests/test_demo_flow.py::TestADBBridgeCore::test_run_command_raises_on_timeout PASSED
tests/test_demo_flow.py::TestDeviceConnection::test_is_device_connected_true PASSED
...
============================== 30 passed in 0.42s ==============================
```

All tests use mocked ADB calls — no phone required.

---

## Troubleshooting

### "No devices/emulators found"
```bash
# Restart the ADB server
adb kill-server
adb start-server
adb devices
```

### "device unauthorized"
1. Unlock your phone
2. Check for the "Allow USB debugging?" dialog
3. Tap **Allow** (check "Always allow from this computer")

### "adb: command not found"
ADB isn't in your PATH. Install platform tools and ensure the folder is added:
```bash
# Mac (homebrew)
brew install android-platform-tools

# Verify
which adb
```

### "error: insufficient permissions"
On Linux, add yourself to the `plugdev` group:
```bash
sudo usermod -aG plugdev $USER
# Log out and back in
```

Or create a udev rule:
```bash
echo 'SUBSYSTEM=="usb", ATTR{idVendor}=="18d1", MODE="0666", GROUP="plugdev"' | \
  sudo tee /etc/udev/rules.d/51-android.rules
sudo udevadm control --reload-rules
```

### SMS doesn't actually send
The demo uses `am start ACTION_SENDTO` — this opens the SMS compose view. Some Android versions require the app to already be the default SMS app. For the demo:
- Use your own phone number as recipient
- Or switch to `--sim` mode for presentation

### Voice doesn't play
edge-tts generates audio but you need a media player:
```bash
# Linux
sudo apt install mpg123

# Mac
# afplay is built-in

# Or just let the demo run silently — it still looks great
```

### Demo crashes on import
```bash
cd /path/to/aria-os
# Make sure you're running from the project root
python demo/demo.py --sim
```

---

## Demo Day Checklist

```
Pre-demo:
[ ] Phone charged > 50%
[ ] USB debugging enabled and authorized
[ ] `adb devices` shows your phone as "device"
[ ] `python demo/demo.py --sim` runs cleanly (dry run)
[ ] ANTHROPIC_API_KEY set (optional but recommended)
[ ] Terminal: font size 16+, window maximized, dark theme
[ ] Speakers tested (for Aria's voice)
[ ] Read demo/DEMO_SCRIPT.md

Day-of:
[ ] Plug in phone, confirm adb devices
[ ] Open terminal in aria-os/ directory
[ ] python demo/demo.py
[ ] Breathe. Let Aria impress.
```

---

## Project Structure

```
aria-os/
├── agent/
│   ├── android/
│   │   ├── adb_bridge.py       ← Core ADB wrapper (fully functional)
│   │   ├── app_launcher.py     ← App control
│   │   ├── notifications.py    ← Notification reader
│   │   └── screen_reader.py    ← Screenshot / vision
│   ├── tools/
│   │   └── implementations/
│   │       ├── sms_tool.py     ← SMS send/read
│   │       ├── contacts_tool.py
│   │       ├── calendar_tool.py
│   │       └── ...
│   ├── aria_agent.py           ← Main agent loop
│   └── voice/
│       └── pipeline.py         ← edge-tts voice output
├── demo/
│   ├── demo.py                 ← 🎯 Run this for the demo
│   ├── DEMO_SCRIPT.md          ← Omar's talking points
│   └── setup.sh                ← One-command setup
├── tests/
│   └── test_demo_flow.py       ← Integration tests (no phone needed)
└── docs/
    ├── ARCHITECTURE.md
    └── DEMO_SETUP.md           ← This file
```

---

*Aria OS v0.1 — Built for demo day. Questions? omar@aria-os.ai*
