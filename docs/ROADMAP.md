# Aria OS — Roadmap

## Vision

An AI that runs entirely on your Android device — not as a chat app that delegates to the cloud, but as the actual OS layer. Aria sees what you see, acts as you act, and learns your patterns over time.

---

## Phase 1 — Core Agent (v0.1) ✅

**Goal:** Working AI assistant on Android, accessible from any app.

### Completed
- [x] `AriaAgentService` — persistent foreground service
- [x] `ClaudeClient` — direct HTTPS to Anthropic API
- [x] `ToolRegistry` — dynamic tool dispatch
- [x] 12 native Android tools (SMS, calls, contacts, calendar, browser, maps, weather, music, settings, notifications, search, app launcher)
- [x] `AriaAccessibilityService` — reads/controls any app
- [x] `AriaVoice` — TTS responses (Android TextToSpeech)
- [x] `WakeWordDetector` — continuous "Hey Aria" detection
- [x] Flutter UI — chat screen, voice screen, settings
- [x] Room database — conversation history + memory facts
- [x] Boot receiver — auto-start on device boot

### Known Limitations
- Wake word uses SpeechRecognizer (requires internet for Google ASR)
- Conversation context cleared on service restart
- Tools require user to have granted all permissions manually

---

## Phase 2 — Proactive AI (v0.2) 🔲

**Goal:** Aria acts without being asked, learns patterns, surfaces insights.

### Features
- [ ] **Location awareness** — Aria knows when you arrive/leave home, work, gym
- [ ] **Calendar-driven proactivity** — "You have a meeting in 30 min, traffic is bad, leave now"
- [ ] **Notification intelligence** — Summarize, triage, and respond to notifications
- [ ] **Habit tracking** — Learns daily patterns (morning alarm, workout time, etc.)
- [ ] **Conversation persistence** — Context survives service restarts via Room DB
- [ ] **Memory engine** — Extracts and stores key facts ("My wife's name is Sara", "I work at Acme Corp")
- [ ] **Proactive reminders** — "You said you'd call your doctor. It's been 3 days."
- [ ] **App usage intelligence** — Sees which apps you use and when, optimizes suggestions
- [ ] **Smart notifications** — Custom notification cards with Aria's summaries

### Technical
- Room database schema v2 with richer memory model
- LocationManager integration
- NotificationListenerService (full notification access)
- WorkManager for background tasks

---

## Phase 3 — On-Device LLM (v0.3) 🔲

**Goal:** Aria runs offline. No cloud dependency for core functions.

### Features
- [ ] **Whisper JNI** — On-device speech recognition (no Google ASR)
- [ ] **Local LLM** — Llama 3 / Phi-3 via llama.cpp Android port
  - Fast queries: local model (< 500ms)
  - Complex queries: Claude API (when online)
  - Routing logic: query classifier decides local vs cloud
- [ ] **On-device embeddings** — Vector memory search
- [ ] **Fully offline mode** — Core tools work without internet
- [ ] **Reduced battery usage** — Smarter wake word with ML model

### Technical
- JNI bridge to llama.cpp (C++ → Kotlin)
- ONNX Runtime for ML models
- Quantized 4-bit models (fits in 4GB RAM)
- Whisper.cpp via JNI

---

## Phase 4 — Aria Launcher (v0.4) 🔲

**Goal:** Aria replaces the Android launcher. It IS the home screen.

### Features
- [ ] **Custom launcher** — Home screen built around Aria
- [ ] **Always-on overlay** — Persistent Aria button on every screen
- [ ] **Visual AI** — Camera input → Claude Vision → screen understanding
- [ ] **Full gesture control** — Navigate entirely by voice + AI
- [ ] **App cloning** — AI creates shortcuts for frequent multi-step tasks
- [ ] **Screen recording + summarization** — "What did I look at today?"
- [ ] **Aria Widgets** — Smart home screen cards powered by AI
- [ ] **Multi-device sync** — Aria context syncs across your devices

### Technical
- Custom launcher (`android.intent.category.HOME`)
- System overlay permissions (TYPE_APPLICATION_OVERLAY)
- Camera2 API for visual input
- MediaProjection API for screen capture
- End-to-end encryption for sync

---

## Long-Term Vision (v1.0+)

- **Aria Skills** — Plugin system for community-built tools
- **Cross-app workflows** — Multi-step automations across any app
- **Predictive UI** — Aria starts doing things before you ask
- **Personal AI model** — Fine-tuned on your own data (on-device)
- **Open ecosystem** — Developers build Aria-native apps

---

## Contributing to the Roadmap

Have an idea? Open an issue with:
- What the feature does
- Which phase it belongs in
- What Android APIs it needs
- Any privacy/security considerations

The core principle: **everything runs on your device, under your control.**
