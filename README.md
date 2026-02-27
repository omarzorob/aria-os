# Aria OS

**An AI-native Android assistant.** Talk or type — your phone does the rest.

No app-switching. No copy-pasting. Just results.

---

## What it does

You talk to Aria. Aria does things.

- "Email John that I'll be 10 minutes late"
- "Order my usual from Chipotle"
- "What's the weather this weekend in Chicago?"
- "Text mom I'm on my way"
- "Research the best standing desks under $500 and summarize them"
- "Set a reminder for Dhuhr prayer"
- "Find me a halal restaurant nearby with 4+ stars and order delivery"
- "Play something chill"
- "Call Dr. Ahmed's office and schedule an appointment for next Tuesday"

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                        USER INTERFACES                            │
│                                                                  │
│     Flutter UI (chat + voice)    │    CLI (aria_agent.py)        │
│          HTTP + WebSocket        │     direct Python             │
└──────────────────────┬───────────────────────┬───────────────────┘
                       │                       │
                       ▼                       ▼
┌─────────────────────────────────────────────────────────────────┐
│              AGENT HTTP SERVER — :8765  (server.py)              │
│                                                                  │
│  POST /chat  GET /health  GET /status  POST /voice/transcribe    │
│  WS   /stream (token streaming)                                  │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                       ARIA AGENT CORE                            │
│                                                                  │
│   LLM Client ──► Claude (Anthropic) or GPT-4 (OpenAI)           │
│   Session Memory ──► token-budgeted conversation history         │
│   Tool Executor ──► validate → rate-limit → execute              │
└──────────────────────────────┬──────────────────────────────────┘
                               │ tool calls
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                         14 CORE TOOLS                            │
│                                                                  │
│  SMS │ Email │ Phone │ Contacts │ Calendar │ Reminders           │
│  WebSearch │ Browser │ Maps │ Food │ Grocery │ Weather           │
│  Music │ Settings                                                │
│                                                                  │
│  Auto-discovered by ToolLoader from agent/tools/implementations/ │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                    ANDROID CONTROL LAYER                          │
│                                                                  │
│  ADBBridge (USB/WiFi)  ──►  Android Device                       │
│  ADBManager (auto-reconnect, multi-device)                       │
│  Accessibility Service (screen reading, UI automation)           │
│  Intent System │ Content Providers (SMS, Contacts, Calendar)     │
└─────────────────────────────────────────────────────────────────┘
```

---

## Features

### Phase 1 — Completed ✅
| Feature | File |
|---|---|
| ADB bridge (tap, swipe, type, screenshot) | `agent/android/adb_bridge.py` |
| Accessibility service (screen reader) | `agent/android/accessibility_service.py` |
| App launcher | `agent/android/app_launcher.py` |
| Notification reader | `agent/android/notifications.py` |
| 14 core tools | `agent/tools/implementations/` |
| Flutter UI (chat + voice + task progress) | `apps/aria_ui/` |
| Core agent (AriaAgent class) | `agent/aria_agent.py` |

### Phase 2 — Completed ✅
| Feature | File |
|---|---|
| FastAPI HTTP server + WebSocket streaming | `agent/server.py` |
| Auto-discover + register all tools | `agent/tool_loader.py` |
| LLM client (Anthropic + OpenAI, tool calling) | `agent/llm/client.py` |
| Aria system prompt | `agent/llm/prompts.py` |
| Session memory with token budgeting | `agent/memory/session.py` |
| Wake word detection (Porcupine + ADB fallback) | `agent/voice/wake_word.py` |
| Safe tool execution engine with rate limiting | `agent/executor.py` |
| ADB device manager + auto-reconnect | `agent/android/adb_manager.py` |
| Unit tests — 35+ tests for all 14 tools | `tests/test_tools.py` |
| Docker setup (Dockerfile + compose) | `docker/` |
| Main agent entry point | `agent/main_agent.py` |
| Technical architecture docs | `docs/ARCHITECTURE.md` |

---

## 14 Core Tools

| Tool | Description |
|---|---|
| **SMS** | Send / read text messages via ADB content provider |
| **Email** | Send / search emails via Gmail or default mail app |
| **Phone** | Make calls, view call history |
| **Contacts** | Search and look up contacts |
| **Calendar** | Create events, view today's schedule |
| **Reminders** | Set alarms, timers, and reminders |
| **Web Search** | Search the web, return summarised results |
| **Browser** | Open URLs in Chrome, read page content |
| **Maps** | Get directions, ETA, search nearby places |
| **Food Order** | Browse restaurants, order delivery via UberEats |
| **Grocery** | Search products, manage cart, order groceries |
| **Weather** | Current conditions + multi-day forecast |
| **Music** | Play/pause/skip, control volume, search tracks |
| **Settings** | Toggle WiFi, Bluetooth, DND, brightness, volume |

---

## Setup Guide

### Requirements

- Python 3.12+
- Android device with USB debugging enabled (or ADB over WiFi)
- `adb` in PATH (`android-tools-adb` or Android SDK Platform Tools)
- Anthropic or OpenAI API key

### Quick Start

```bash
git clone https://github.com/omarzorob/aria-os
cd aria-os

# Install uv (fast Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install all dependencies
uv sync

# Configure API keys
export ANTHROPIC_API_KEY=sk-ant-your-key-here
# or: export OPENAI_API_KEY=sk-your-openai-key

# Optional: target a specific Android device
export ARIA_ADB_SERIAL=emulator-5554

# Start the Aria agent server
python -m agent.main_agent
```

Server starts at `http://0.0.0.0:8765`.

### API Usage

```bash
# Chat with Aria
curl -X POST http://localhost:8765/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What time is it in Tokyo?"}'

# Health check
curl http://localhost:8765/health

# Agent status
curl http://localhost:8765/status
```

### Docker

```bash
# Create your environment file
cat > .env <<EOF
ANTHROPIC_API_KEY=sk-ant-your-key-here
ARIA_PORT=8765
EOF

# Start with Docker Compose
docker compose -f docker/docker-compose.yml up --build
```

> **For Android device access in Docker:** pass `--device /dev/bus/usb` to `docker run`  
> for USB-connected devices, or use ADB over WiFi:  
> set `ANDROID_SERIAL=<device-ip>:5555` and connect with `adb connect <ip>:5555`.

### Run Tests

```bash
# Run all unit tests (no Android device required)
uv run pytest tests/ -v

# Run specific test class
uv run pytest tests/test_tools.py::TestSMSTool -v
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| OS base | GrapheneOS / AOSP |
| Agent server | FastAPI + uvicorn |
| LLM | Claude (Anthropic) → GPT-4 (OpenAI) fallback |
| Voice → Text | OpenAI Whisper (on-device) |
| Text → Voice | edge-tts / Kokoro |
| Phone control | ADB (USB + WiFi) + Accessibility Service |
| Memory | Session memory (JSON) + SQLite long-term |
| UI | Flutter (chat + voice) |
| Containerisation | Docker + Docker Compose |

---

## Project Roadmap

### ✅ Phase 1 — Agent on Android
Core tools, ADB control layer, Flutter UI, voice pipeline

### ✅ Phase 2 — HTTP Server + Deep Integration
FastAPI server, LLM client abstraction, session memory, Docker, 35+ tests

### 🔜 Phase 3 — Deep OS Integration
- GrapheneOS fork with Aria pre-installed
- On-device LLM (no cloud dependency)
- Multi-step task planning
- Browser automation (forms, payments)

### 🔜 Phase 4 — Full Autonomy
- Third-party skill system
- Cross-device sync (phone ↔ desktop)
- Community plugin marketplace

---

## Why this matters

Every phone assistant today is deliberately crippled:
- Siri can't send emails without your approval
- Google Assistant can't see what's on your screen
- They're designed to keep you in the app ecosystem

Aria has no such limitations. It's your agent, not Apple's or Google's.

---

## Contributing

Built in public. PRs welcome. See `CONTRIBUTING.md`.

Full technical documentation: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)

License: Apache 2.0
