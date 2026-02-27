# Aria OS

**An AI-native Android assistant that runs entirely on your device.**

Aria is a persistent foreground service + Flutter UI that connects to Claude AI directly from your phone. No cloud relay, no laptop bridge, no Python backend — everything runs natively on Android using Kotlin + Flutter.

---

## What Aria Does

- 🎙️ Listens for "Hey Aria" via Android SpeechRecognizer
- 🧠 Sends your request to Claude API over HTTPS from the device
- 🔧 Executes tool calls using native Android APIs (SMS, calls, calendar, etc.)
- 🔊 Speaks the response back using Android TTS
- 💬 Shows a persistent chat UI (Flutter)
- ♿ Reads and controls any app via Accessibility Service

---

## Architecture Overview

```
Flutter UI (Dart)
      ↕  MethodChannel
AriaAgentService (Kotlin)
      ↕  HTTPS
Claude API (Anthropic)
      ↕  Tool calls
Android Tools (SMS, Contacts, Calendar, Maps, …)
```

All IPC is Android-native: `MethodChannel`, `Intent`, `Broadcast`. No sockets, no bridges.

---

## Quick Start

### Prerequisites

- Android Studio (Hedgehog or later)
- Flutter SDK 3.16+
- ADB (for sideloading)
- Android phone, Android 9+ (API 28+), rooted preferred for full permissions

### Build

```bash
cd aria-app
flutter pub get
flutter build apk --debug
# APK → aria-app/build/app/outputs/flutter-apk/app-debug.apk
```

Or use the script:

```bash
bash scripts/build.sh
```

### Install

```bash
adb install -r aria-app/build/app/outputs/flutter-apk/app-debug.apk
```

Or:

```bash
bash scripts/install.sh
```

### Configure

1. Open Aria on your phone
2. Go to Settings → Enter your Claude API key
3. Go to Android Settings → Accessibility → Installed Services → Aria → Enable
4. Tap the Aria launcher or say "Hey Aria"

Full setup guide: [docs/SETUP.md](docs/SETUP.md)

---

## Phase Roadmap

| Phase | Status | Features |
|-------|--------|---------|
| 1 — Core Agent | ✅ v0.1 | Claude API, tools, voice I/O, accessibility |
| 2 — Proactive AI | 🔲 | Location awareness, smart notifications, habits |
| 3 — On-Device LLM | 🔲 | Whisper JNI, local small model fallback |
| 4 — Aria Launcher | 🔲 | Replace Android launcher entirely |

Full roadmap: [docs/ROADMAP.md](docs/ROADMAP.md)

---

## Tools Available

| Tool | Android API |
|------|-------------|
| `send_sms` | SmsManager |
| `make_call` | Intent ACTION_CALL |
| `search_contacts` | ContactsContract |
| `get_calendar_events` | CalendarContract |
| `launch_app` | PackageManager |
| `open_browser` | Intent ACTION_VIEW |
| `get_weather` | Open-Meteo API |
| `get_directions` | Google Maps Intent |
| `control_music` | AudioManager KeyEvents |
| `change_setting` | Settings.System / AudioManager |
| `get_notifications` | AccessibilityService |
| `web_search` | DuckDuckGo API |

---

## Contributing

1. Fork → feature branch → PR
2. All agent logic goes in Kotlin (`aria-app/android/app/src/main/kotlin/ai/aria/`)
3. All UI goes in Dart (`aria-app/lib/`)
4. New tools: extend `AriaTool`, register in `ToolRegistry`
5. No Python. No ADB bridges. Android APIs only.

---

## License

Apache 2.0 — see [LICENSE](LICENSE)
