# Aria OS Architecture

## Overview

Aria is an AI agent that runs at the OS level on Android. It understands natural language (voice or text), reasons about what you want, and controls your phone to make it happen — without you touching any apps.

```
┌──────────────────────────────────────────────────────┐
│                    User Interface                     │
│        Voice (Whisper)  │  Chat (Flutter UI)          │
└───────────────────────────┬──────────────────────────┘
                            │
┌───────────────────────────▼──────────────────────────┐
│                   Aria Agent Core                     │
│                                                       │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────┐  │
│  │  Intent     │  │     LLM      │  │   Memory    │  │
│  │  Parser     │→ │  (Claude /   │→ │  (SQLite +  │  │
│  │             │  │   Local)     │  │   Vector)   │  │
│  └─────────────┘  └──────┬───────┘  └─────────────┘  │
│                          │                            │
│  ┌───────────────────────▼──────────────────────────┐ │
│  │               Tool Router                        │ │
│  └──┬──────┬──────┬──────┬──────┬──────┬────────────┘ │
└─────┼──────┼──────┼──────┼──────┼──────┼─────────────┘
      │      │      │      │      │      │
      ▼      ▼      ▼      ▼      ▼      ▼
    SMS   Email  Browser  Maps  Order  Custom
                                       Tools
      │      │      │      │      │      │
┌─────▼──────▼──────▼──────▼──────▼──────▼─────────────┐
│              Android System Layer                      │
│                                                       │
│   Accessibility Service  │  ADB Bridge                │
│   Intent System          │  Content Providers         │
│   Notification Manager   │  Telephony Manager         │
└───────────────────────────────────────────────────────┘
```

---

## Components

### 1. Voice Pipeline
- **Input**: Whisper (on-device, `base` model by default, upgradeable)
- **Wake word**: Porcupine or custom keyword detection
- **VAD**: Silero VAD — detects when user stops speaking
- **Output**: edge-tts (Phase 1-2) → Kokoro/on-device TTS (Phase 3)

### 2. Agent Core (`agent/aria_agent.py`)
The brain. Receives text input, reasons about intent, calls tools, returns a response.

- Uses Claude API (Phase 1-2) or local LLM via llama.cpp (Phase 3)
- Maintains conversation history with sliding window
- Calls tools using Claude's native tool-use API
- Plans multi-step tasks when needed

### 3. Memory System (`agent/memory/`)
Aria remembers you across sessions.

```
memory/
├── short_term.py    # Current conversation context
├── long_term.py     # SQLite — facts about user, preferences, history
└── semantic.py      # Vector store — fuzzy recall ("that restaurant I liked")
```

### 4. Tool Registry (`agent/tool_registry.py`)
Tools are the actions Aria can take. Each tool:
- Has a name, description, and JSON schema (for LLM)
- Has an `execute(inputs) -> str` method
- Is registered at startup, discovered automatically

```
tools/
├── base.py           # Tool base class
├── sms.py            # Send/read SMS
├── email.py          # Send email
├── phone.py          # Make/receive calls
├── browser.py        # Web browsing
├── maps.py           # Navigation
├── food_order.py     # UberEats / DoorDash
├── grocery.py        # Instacart
├── calendar.py       # Events and reminders
├── music.py          # Spotify / YouTube Music
├── settings.py       # System settings
└── screen.py         # Read/control screen UI
```

### 5. Android Control Layer
Two mechanisms for controlling the phone:

**Accessibility Service** (preferred):
- Reads all UI elements on screen
- Can tap, swipe, type into any app
- No root required
- Lives in `system/accessibility/AriaAccessibilityService.kt`

**ADB Bridge** (fallback / Phase 1):
- Full shell access
- Used when device is connected to desktop
- `system/adb_bridge.py`

### 6. Custom Launcher (`apps/launcher/`)
Phase 2+. Replaces the Android home screen.
- Aria chat is the home screen
- No app drawer needed — just ask
- Built in Flutter

---

## Data Flow — Example: "Order me a burger from McDonald's"

```
1. Voice captured → Whisper → "Order me a burger from McDonald's"
2. Agent receives text, checks memory (do I have a saved McDonald's order?)
3. LLM reasons: use food_order tool with restaurant="McDonald's", items="burger"
4. Tool router calls food_order.execute()
5. food_order opens UberEats via ADB, searches McDonald's
6. Accessibility Service reads menu, finds "Quarter Pounder"
7. Taps Add to Cart → Checkout → confirms address → places order
8. Agent replies: "Done — Quarter Pounder ordered, arriving in 30 mins"
9. Response → edge-tts → spoken back to user
```

---

## Phase 3: On-Device LLM

Target: Run a capable LLM locally on Pixel 8 Pro (12GB RAM).

- **Model candidates**: Gemma-3 4B, Llama-3.2 3B, Phi-3 Mini
- **Runtime**: llama.cpp (Android port) or ExecuTorch
- **Hybrid mode**: Route simple tasks local, complex to cloud
- **Privacy mode**: 100% offline — nothing leaves the device

---

## Security Model

- Agent runs as system service with elevated permissions (Phase 2+)
- All tool execution is logged
- User can review and revoke any action in history
- Payment actions require explicit confirmation
- No data sent to cloud in Phase 3 privacy mode
