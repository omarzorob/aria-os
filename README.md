# Aria OS

**An AI-native mobile operating system.** Talk or type — your phone does the rest.

Built on AOSP (GrapheneOS base). The OS gets out of your way. The agent runs your life.

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

No app-switching. No copy-pasting. Just results.

---

## Architecture

```
┌─────────────────────────────────────┐
│           User Interface            │
│  Voice (Whisper) │ Chat (Aria UI)   │
└──────────────────┬──────────────────┘
                   │
┌──────────────────▼──────────────────┐
│           Aria Agent Core           │
│  Intent Parser → Tool Router        │
│  Memory │ Context │ Session         │
└──┬───┬───┬───┬───┬───┬─────────────┘
   │   │   │   │   │   │
   ▼   ▼   ▼   ▼   ▼   ▼
 Email SMS Call Maps Order Research
   │   │   │   │   │   │
┌──▼───▼───▼───▼───▼───▼─────────────┐
│         Android System Layer        │
│  Accessibility Service │ ADB Bridge │
│  Intent System │ Content Providers  │
└─────────────────────────────────────┘
```

---

## Base OS

- **Foundation:** [GrapheneOS](https://grapheneos.org/) (hardened AOSP, privacy-first)
- **Target hardware (Phase 1):** Google Pixel 7/8 (best AOSP support)
- **Display:** Custom launcher replacing default home screen
- **No Google services by default** — optional sandboxed Google Play

---

## Tech Stack

| Layer | Tech |
|---|---|
| OS Base | GrapheneOS / AOSP |
| Agent Core | Python / Rust |
| LLM | Claude API (cloud) → local model (Phase 3) |
| Voice → Text | Whisper (on-device) |
| Text → Voice | edge-tts / Kokoro (on-device) |
| Phone Control | Android Accessibility Service + ADB |
| App Automation | UiAutomator2 / Accessibility APIs |
| Memory | SQLite + vector store |
| UI | React Native / Flutter launcher app |

---

## Roadmap

### Phase 1 — Agent on Android (3 months)
*Prove the concept. Works on any rooted Android.*

- [ ] Aria agent app (foreground service, always-on)
- [ ] Voice input (Whisper on-device)
- [ ] Voice output (edge-tts)
- [ ] Core tools: SMS, email, reminders, timer, alarm
- [ ] Android Accessibility Service for screen reading
- [ ] Basic app control (open apps, tap UI elements)
- [ ] Persistent memory (remembers you across sessions)
- [ ] GitHub repo + docs open sourced

### Phase 2 — Deep OS Integration (3 months)
*Fork GrapheneOS. Go deeper than any app can.*

- [ ] GrapheneOS fork with Aria pre-installed
- [ ] Custom launcher (Aria-first home screen)
- [ ] System-level permissions (no user prompts)
- [ ] Background agent always running
- [ ] Phone call automation (place + receive calls)
- [ ] Browser control (navigate, fill forms, extract info)
- [ ] Payment automation (Google Pay / in-app)
- [ ] Calendar deep integration

### Phase 3 — Full Autonomy (6 months)
*The agent does everything. You just intent.*

- [ ] On-device LLM (no cloud dependency)
- [ ] Multi-step task planning ("order groceries" → searches store → picks items → checks out)
- [ ] App ecosystem (Aria-native apps that expose clean APIs to the agent)
- [ ] Third-party skill system (developers build Aria tools)
- [ ] Cross-device sync (phone ↔ desktop agent)
- [ ] Community plugin marketplace

### Phase 4 — Hardware (TBD)
- [ ] Custom device partnership or reference design
- [ ] Aria OS pre-installed, no flashing required

---

## Getting Started (Phase 1)

```bash
git clone https://github.com/[org]/aria-os
cd aria-os/agent
pip install -r requirements.txt
# Configure your API key
cp config.example.json config.json
# Run on connected Android device
adb install aria-accessibility.apk
python aria_agent.py
```

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

License: Apache 2.0
