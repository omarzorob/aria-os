# 🎤 Aria OS — Business Partner Demo Script

> **Omar's cheat sheet for the demo meeting.**  
> Read this the night before. Bring confidence. Let Aria do the heavy lifting.

---

## ⏱️ Timeline Overview

| Section | Time |
|---------|------|
| Opening pitch | 0:30 |
| Live demo walkthrough | 5:00 |
| Q&A | 3:00 |
| **Total** | **~9 minutes** |

---

## 🚀 Opening Pitch (30 seconds)

> Say this while the terminal is loading. Make eye contact.

---

*"Let me show you something that doesn't exist yet — but should.*

*Your phone has more computing power than the computers that sent humans to the moon. But you still tap through 5 menus to send a text.*

*Aria changes that. It's an AI agent that runs on your laptop and controls your Android phone — completely. Not just voice commands. Full control: SMS, apps, contacts, alarms, notifications — all from natural language.*

*This is what I'm building. Let me show you."*

---

## 📱 Live Demo Walkthrough (5 minutes)

### Setup (30 sec before partners arrive)
```bash
cd /path/to/aria-os
python demo/demo.py
```

> Phone should be plugged in, screen on. Terminal maximized. Font size 16+.

---

### Step 1 — Connect (30 sec)

**Say:** *"First, Aria finds your phone automatically. No setup, no config."*

> Watch the spinner animate as ADB detects the device.

**Say:** *"That's a live USB connection. Aria is now in control."*

---

### Step 2 — Device Info (30 sec)

**Say:** *"Aria knows everything about your device — model, OS version, battery. It uses this context to make smarter decisions."*

> Point at the battery level.

**Say:** *"If battery is low, Aria automatically adjusts — skips media-heavy tasks, prioritizes quick wins."*

---

### Step 3 — Send SMS (45 sec)

**Say:** *"Let me show you the most basic thing — sending a text. But watch HOW Aria does it."*

> Watch the demo send the SMS.

**Say:** *"One command. No unlock, no app switch, no tap tap tap. Aria handles all the ADB intents in the background. The recipient gets a real text message."*

---

### Step 4 — Live Weather + Voice (30 sec)

**Say:** *"Aria doesn't just control your phone — it's your personal intelligence layer. Here it fetches live weather..."*

> Let Aria's voice play through the speakers.

**Say:** *"That's Aria's actual voice. Neural TTS. Sounds human. This is how Aria will narrate your morning briefing, read notifications, give you directions — all hands-free."*

---

### Step 5 — Screenshot (30 sec)

**Say:** *"Aria can see your screen at any time. This isn't screen mirroring — it's actual pixel data that Aria can analyze."*

> The screenshot renders in terminal.

**Say:** *"In the full product, Aria uses computer vision on this. It can read UI elements, detect what app is open, and navigate autonomously."*

---

### Step 6 — Contacts Search (20 sec)

**Say:** *"Natural contact search. Say a name, get a result. No keyboard, no fumbling."*

---

### Step 7 — Set Alarm (20 sec)

**Say:** *"Alarm set. 8 AM. Tomorrow. One line of intent. This is how Aria handles your whole morning routine — automatically."*

---

### Step 8 — Launch App (15 sec)

**Say:** *"Any app, instantly. Aria can chain these — open Spotify, search for a playlist, hit play — all in one command."*

---

### Step 9 — Notifications (30 sec)

**Say:** *"Aria reads your notifications and surfaces what matters. In the full product, it triage these — urgent vs. noise — and only interrupts you for the important ones."*

---

### Step 10 — Interactive Mode (90 sec)

> This is the money shot. Type a real command, live.

**Say:** *"Now I'm going to hand it over to Aria completely."*

Type: `Send a text to Mom saying I'll be home by 7`

> Watch Aria respond and take action.

**Say:** *"That just happened. Natural language → real action on a real phone. No shortcuts, no fake UI."*

Type: `What's on my calendar today?`

**Say:** *"Aria integrates with everything — calendar, contacts, SMS, apps. It's not an app. It's the intelligence layer over all your apps."*

---

## 💡 Key Talking Points

### What makes Aria different?

- **AI-native, not AI-added.** Other phones bolt AI onto existing UI. Aria replaces the UI with intelligence.
- **Any Android phone.** No custom ROM, no special hardware. Works on your phone today via USB, WiFi tomorrow.
- **Voice-first, but not voice-only.** Aria works via voice, text, or API — choose your interface.
- **Developer platform.** Third-party devs can build Aria Skills — like apps, but smarter.

### The business model

- **Consumer:** Subscription app — $9.99/month. Aria as your daily driver.
- **Enterprise:** Fleet management — IT teams control employee devices via Aria API.
- **Platform:** Revenue share on Aria Skills marketplace (like App Store, but for AI actions).

---

## ❓ Q&A Talking Points

**"What stops Apple/Google from doing this?"**
> They have regulatory capture — they're legally constrained from tying AI deeply into competitors' devices the way we can. We're also 3 years ahead of where they'll get to. And our model is open — we work WITH Android, not against it.

**"Why USB? That's limiting."**
> USB is the demo. Production is ADB-over-WiFi and our lightweight on-device agent. We needed to prove the concept works first — and it does. Wireless version is in progress.

**"What about privacy? You have full phone access."**
> Aria runs locally. No phone data leaves the device unless the user explicitly asks Aria to share it. It's architecturally private — we don't even have servers to store it on.

**"How big is the market?"**
> 3 billion Android phones. Even at 0.1% penetration and $10/month, that's $36M ARR. Enterprise is another story — Fortune 500 companies pay $50K+/year for RPA solutions that don't work half as well.

**"What's your moat?"**
> First-mover in AI-native Android control. The accessibility service integration is deeply technical — 6 months of work. The voice pipeline is custom-tuned. And we're building network effects through the Skills marketplace.

**"What do you need from us?"**
> [Fill in based on the meeting: investment, partnership, distribution, etc.]

---

## 🎯 Vision Slide (ASCII)

```
╔══════════════════════════════════════════════════════════════════╗
║                                                                  ║
║                    ARIA OS — FULL VISION                         ║
║                                                                  ║
║  Today (Demo):              6 Months:           2 Years:         ║
║  ┌─────────────┐            ┌──────────────┐    ┌─────────────┐  ║
║  │  Laptop     │            │  Aria App    │    │  Aria OS    │  ║
║  │  + ADB      │            │  on-device   │    │  Full ROM   │  ║
║  │  ─────────  │            │  WiFi/BT     │    │  No Android │  ║
║  │  Controls   │    ───▶    │  ──────────  │ ─▶ │  ─────────  │  ║
║  │  Android    │            │  Autonomous  │    │  AI-first   │  ║
║  │  via USB    │            │  all day     │    │  from boot  │  ║
║  └─────────────┘            └──────────────┘    └─────────────┘  ║
║                                                                  ║
║  Skills Marketplace:  SMS · Calendar · Maps · Music · Finance    ║
║                       Shopping · Health · Smart Home · ...       ║
║                                                                  ║
║  Revenue:   Consumer $10/mo  │  Enterprise $50K/yr  │  Platform  ║
║                                                                  ║
║  "The AI that lives inside your phone."                          ║
╚══════════════════════════════════════════════════════════════════╝
```

---

## ✅ Pre-Demo Checklist

- [ ] Phone charged > 50%
- [ ] USB debugging enabled (Settings → Developer Options → USB Debugging)
- [ ] Phone unlocked and on home screen
- [ ] `python demo/demo.py` runs without errors
- [ ] Terminal font size 16+, window maximized
- [ ] Speakers working (for Aria voice)
- [ ] WiFi on laptop (for live weather)
- [ ] ANTHROPIC_API_KEY set (for live AI responses in interactive mode)
- [ ] Demo SMS recipient is your own number (to avoid awkward messages)

---

## 🆘 If Things Go Wrong

**Phone not detected:**
> "Let me switch to simulation mode — same capabilities, just showing you what it looks like with a live device." `python demo/demo.py --sim`

**ADB crashes:**
> Unplug/replug phone. Run `adb kill-server && adb start-server`. 30 seconds max.

**Voice doesn't play:**
> Not a problem — the text output tells the whole story. Just read Aria's response aloud yourself.

**Interactive AI response is slow:**
> "Aria is reasoning about the best approach..." — buy 10 seconds, it'll be worth it.

---

*Built with Aria OS v0.1 — demo ready as of Feb 2026.*
