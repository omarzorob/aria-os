# Aria OS — Technical Architecture

## Overview

Aria OS is an AI-native Android assistant built on the ADB control layer. Unlike conventional phone assistants, Aria has deep, programmatic access to every aspect of the Android system — no app-switching, no confirmations, just results.

---

## System Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                        USER INTERFACES                                │
│                                                                      │
│   ┌─────────────────┐      ┌──────────────────────────────────┐     │
│   │  Flutter UI App  │      │       CLI / Python REPL          │     │
│   │  (chat + voice)  │      │      (agent/aria_agent.py)       │     │
│   └────────┬────────┘      └────────────────┬─────────────────┘     │
│            │ HTTP/WS                         │ direct Python call     │
└────────────│─────────────────────────────────│──────────────────────┘
             │                                 │
             ▼                                 ▼
┌──────────────────────────────────────────────────────────────────────┐
│                       AGENT HTTP SERVER (P2-1)                        │
│                        agent/server.py  :8765                         │
│                                                                      │
│   POST /chat           → run agent, return response                  │
│   GET  /health         → {"status": "ok"}                            │
│   GET  /status         → agent stats, tool list, memory info          │
│   POST /voice/transcribe → audio bytes → transcript                   │
│   WS   /stream         → streaming token delivery                    │
└─────────────────────────────┬────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────────┐
│                         ARIA AGENT CORE                               │
│                                                                      │
│   ┌──────────────────────────────────────────────────────────────┐   │
│   │              agent/aria_agent.py  (AriaAgent)                │   │
│   │                                                              │   │
│   │   ┌──────────────┐    ┌─────────────────┐                   │   │
│   │   │  LLM Client   │    │  Session Memory  │                   │   │
│   │   │ (P2-3, P2-4) │    │    (P2-5)        │                   │   │
│   │   │              │    │                  │                   │   │
│   │   │  Anthropic ◄─┤    │ get_context_     │                   │   │
│   │   │  OpenAI      │    │ window()         │                   │   │
│   │   └──────┬───────┘    └─────────────────┘                   │   │
│   │          │                                                   │   │
│   │          ▼ tool_calls                                        │   │
│   │   ┌──────────────────────────────────────┐                   │   │
│   │   │      Tool Executor  (P2-7)            │                   │   │
│   │   │    agent/executor.py                  │                   │   │
│   │   │                                      │                   │   │
│   │   │  validate → rate_limit → execute     │                   │   │
│   │   └──────────────────────────────────────┘                   │   │
│   └──────────────────────────────────────────────────────────────┘   │
└──────────────────────────────┬───────────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────────┐
│                          TOOL LAYER                                   │
│                                                                      │
│   Auto-discovered by ToolLoader (P2-2)  agent/tool_loader.py         │
│                                                                      │
│   ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐  │
│   │ SMS  │ │Email │ │Phone │ │Conts │ │Cal   │ │Remdr │ │WSrch │  │
│   └──┬───┘ └──┬───┘ └──┬───┘ └──┬───┘ └──┬───┘ └──┬───┘ └──┬───┘  │
│   ┌──┴───┐ ┌──┴───┐ ┌──┴───┐ ┌──┴───┐ ┌──┴───┐ ┌──┴───┐            │
│   │Brows │ │Maps  │ │Food  │ │Groc  │ │Wthr  │ │Music │            │
│   └──┬───┘ └──┬───┘ └──┬───┘ └──┬───┘ └──┬───┘ └──┬───┘            │
│      │        │        │        │        │        │                  │
│   ┌──┴────────┴────────┴────────┴────────┴────────┴──────────────┐  │
│   │                   ADBBridge  (P1-11)                          │  │
│   │          agent/android/adb_bridge.py                         │  │
│   └──────────────────────────────────────────────────────────────┘  │
└──────────────────────────────┬───────────────────────────────────────┘
                               │  USB / WiFi ADB
                               ▼
┌──────────────────────────────────────────────────────────────────────┐
│                        ADB MANAGER  (P2-8)                            │
│                   agent/android/adb_manager.py                        │
│                                                                      │
│   list_devices() → [DeviceInfo, ...]                                 │
│   get_device()   → ADBBridge (auto-select)                           │
│   auto_reconnect()  → background thread                              │
│   on_connect / on_disconnect → event hooks                           │
└──────────────────────────────┬───────────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────────┐
│                     ANDROID DEVICE LAYER                              │
│                                                                      │
│   ┌────────────────┐  ┌───────────────┐  ┌──────────────────────┐   │
│   │  ADB Shell     │  │  Intents/AM   │  │  Content Providers   │   │
│   │  (input, shell)│  │  (launch apps)│  │  (SMS, Contacts,     │   │
│   │                │  │               │  │   Calendar)          │   │
│   └────────────────┘  └───────────────┘  └──────────────────────┘   │
│                                                                      │
│   ┌────────────────────────────────────────────────────────────┐     │
│   │      Accessibility Service  (P1-12)                        │     │
│   │      agent/android/accessibility_service.py                │     │
│   │      Screen reading, element detection, UI automation      │     │
│   └────────────────────────────────────────────────────────────┘     │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Component Details

### Agent HTTP Server (`agent/server.py`)

FastAPI application serving the Flutter UI and any HTTP clients on port 8765.

| Endpoint | Method | Description |
|---|---|---|
| `/health` | GET | Returns `{"status": "ok", "version": "1.0.0"}` |
| `/status` | GET | Agent stats, active tools, memory info |
| `/chat` | POST | `{"message": "..."}` → `{"response": "..."}` |
| `/voice/transcribe` | POST | Audio upload → `{"transcript": "..."}` |
| `/stream` | WS | Token-streaming chat responses |

CORS is fully open to support local Flutter dev and LAN clients.

---

### LLM Client (`agent/llm/client.py`)

Unified wrapper for Anthropic Claude and OpenAI GPT with structured tool calling.

**Auto-selection logic:**
1. If `ANTHROPIC_API_KEY` is set → use Anthropic Claude (default: `claude-opus-4-6`)
2. If `OPENAI_API_KEY` is set → use OpenAI GPT (default: `gpt-4o`)
3. Override default model with `ARIA_LLM_MODEL` env var

**Key types:**
- `LLMResponse(content, tool_calls, tokens_used, model)`
- `ToolCall(name, arguments, call_id)`

---

### Tool Loader (`agent/tool_loader.py`)

Automatically discovers all `*_tool.py` files in `agent/tools/implementations/` and registers them with the tool registry.

**Discovery flow:**
1. `scan_tools()` — imports each `*_tool.py`, finds classes with `name` + `execute`
2. `register_all(registry, adb)` — instantiates each class, passes ADBBridge if needed
3. `get_tool_manifest()` — returns JSON schema of all tools for inspection

Import errors are caught and logged; the rest of the tools still load.

---

### Tool Executor (`agent/executor.py`)

Executes tool calls from the LLM safely with:
- **Argument validation** — checks required fields against `input_schema`
- **Rate limiting** — sliding 60-second window per tool (default: 30 calls/min)
- **Error isolation** — all exceptions caught, returned as `ToolResult.error`
- **Timing** — measures `duration_ms` for each call
- **Async** — supports both sync and async tool implementations

---

### Session Memory (`agent/memory/session.py`)

Per-conversation memory with token budgeting.

| Method | Description |
|---|---|
| `add_message(role, content)` | Append to history |
| `get_history(max_turns=20)` | Recent messages for LLM |
| `get_context_window(max_tokens=4000)` | Token-budgeted window |
| `summarize()` | Condense old messages |
| `save(path)` / `load(path)` | JSON persistence |

Uses `tiktoken` (cl100k_base encoding) for accurate token counting.  
Falls back to character estimate (1 token ≈ 4 chars) if tiktoken is absent.

---

### ADB Manager (`agent/android/adb_manager.py`)

High-level device lifecycle manager built on top of `ADBBridge`.

- **Multi-device** — list all connected devices, select by serial
- **Auto-reconnect** — background thread polls every N seconds
- **Event hooks** — `on_connect()` / `on_disconnect()` callbacks
- **DeviceInfo** — serial, model, android_version, is_authorized, is_online

---

### Wake Word Detector (`agent/voice/wake_word.py`)

Listens for "Hey Aria" / "Aria" in a background thread.

| Backend | Condition | Notes |
|---|---|---|
| Porcupine SDK | `PORCUPINE_ACCESS_KEY` set | Low-latency, on-device |
| ADB polling | Fallback | Reads `/sdcard/aria_transcription.txt` |

---

## Data Flow — Single Chat Request

```
Flutter UI
  │
  │  POST /chat {"message": "Text Mom I'm on my way"}
  ▼
FastAPI server.py
  │
  │  loop.run_in_executor → AriaAgent.run(message)
  ▼
AriaAgent
  │  1. add_message("user", message) to history
  │  2. LLMClient.complete(history, tools=all_tools)
  ▼
Anthropic Claude API
  │  Response: tool_use → send_sms(to="Mom", message="I'm on my way")
  ▼
ToolExecutor.execute(ToolCall)
  │  1. validate_args → OK
  │  2. rate_limit check → OK
  │  3. SMSTool.send_sms("+15551234567", "I'm on my way")
  ▼
ADBBridge._shell("am start -a android.intent.action.SENDTO ...")
  │
  ▼
Android Device
  │  SMS sent ✓
  ▼
ToolResult(tool_name="send_sms", result="SMS sent to Mom")
  │
  ▼
AriaAgent → second LLM call with tool result
  │
  ▼
Claude: "Sent! 'I'm on my way' → Mom ✓"
  │
  ▼
Flutter UI receives {"response": "Sent! 'I'm on my way' → Mom ✓"}
```

---

## Directory Structure

```
aria-os/
├── agent/
│   ├── android/
│   │   ├── adb_bridge.py         # P1-11: Low-level ADB wrapper
│   │   ├── adb_manager.py        # P2-8:  High-level device manager
│   │   ├── accessibility_service.py # P1-12
│   │   ├── app_launcher.py       # P1-13
│   │   ├── notifications.py      # P1-14
│   │   └── screen_reader.py      # P1-15
│   ├── llm/
│   │   ├── __init__.py           # P2-4
│   │   ├── client.py             # P2-3: LLM client (Anthropic + OpenAI)
│   │   └── prompts.py            # P2-4: System prompt
│   ├── memory/
│   │   ├── long_term.py          # P1: Long-term memory
│   │   └── session.py            # P2-5: Session memory
│   ├── tools/
│   │   ├── base.py               # AriaTool base class
│   │   └── implementations/      # 14 tool implementations
│   │       ├── sms_tool.py
│   │       ├── email_tool.py
│   │       ├── phone_tool.py
│   │       ├── contacts_tool.py
│   │       ├── calendar_tool.py
│   │       ├── reminders_tool.py
│   │       ├── web_search_tool.py
│   │       ├── browser_tool.py
│   │       ├── maps_tool.py
│   │       ├── food_order_tool.py
│   │       ├── grocery_tool.py
│   │       ├── weather_tool.py
│   │       ├── music_tool.py
│   │       └── settings_tool.py
│   ├── voice/
│   │   ├── pipeline.py           # P1: Voice pipeline
│   │   └── wake_word.py          # P2-6: Wake word detection
│   ├── aria_agent.py             # Core agent (AriaAgent class)
│   ├── executor.py               # P2-7: Tool execution engine
│   ├── main_agent.py             # P2-11: Main entry point
│   ├── server.py                 # P2-1: FastAPI HTTP server
│   ├── tool_loader.py            # P2-2: Auto-discovery
│   └── tool_registry.py          # Tool registry
├── apps/
│   └── aria_ui/                  # Flutter UI app
├── docker/
│   ├── Dockerfile                # P2-10
│   ├── docker-compose.yml        # P2-10
│   └── .dockerignore             # P2-10
├── docs/
│   └── ARCHITECTURE.md           # This file
├── tests/
│   └── test_tools.py             # P2-9: Unit tests (35+ tests)
├── pyproject.toml
└── README.md
```

---

## Environment Variables Reference

| Variable | Default | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | Anthropic API key (preferred LLM) |
| `OPENAI_API_KEY` | — | OpenAI API key (fallback LLM) |
| `ARIA_LLM_MODEL` | `claude-opus-4-6` | Override LLM model name |
| `ARIA_HOST` | `0.0.0.0` | Server bind host |
| `ARIA_PORT` | `8765` | Server port |
| `ARIA_MEMORY_PATH` | `memory/session.json` | Session memory file path |
| `ARIA_ADB_SERIAL` | — | Target Android device serial |
| `ARIA_LOG_LEVEL` | `INFO` | Logging level |
| `PORCUPINE_ACCESS_KEY` | — | Picovoice Porcupine SDK key |

---

## Running the Server

### Local

```bash
git clone https://github.com/omarzorob/aria-os
cd aria-os

# Install dependencies (with uv)
uv sync

# Configure
export ANTHROPIC_API_KEY=sk-ant-...

# Start server
python -m agent.main_agent
# or
python agent/main_agent.py
```

Server starts at `http://0.0.0.0:8765`.

### Docker

```bash
# Copy and edit your env vars
cp .env.example .env

# Build and run
docker compose -f docker/docker-compose.yml up --build

# For USB Android device access:
docker run --device /dev/bus/usb aria-os/agent
```

### Flutter Integration

In `apps/aria_ui/`, set the server URL to `http://<host>:8765`.  
The Flutter app communicates via `POST /chat` for text and `WS /stream` for streaming.

---

## Security Notes

- The server binds to `0.0.0.0` by default — restrict to localhost or an internal network in production.
- CORS is fully open; tighten `allow_origins` in `server.py` for production deployments.
- API keys are read from environment variables only — never hardcoded.
- ADB access gives full control over the connected Android device. Ensure physical security.
