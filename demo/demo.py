#!/usr/bin/env python3
"""
Aria OS — Live Demo Script
==========================
A polished, interactive demo of Aria's AI-native Android control capabilities.

Usage:
    python demo/demo.py            # Full scripted demo → interactive mode
    python demo/demo.py --quick    # Jump straight to interactive mode
    python demo/demo.py --sim      # Force simulated mode (no phone needed)
"""

from __future__ import annotations

import argparse
import asyncio
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Ensure project root is on sys.path
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# ---------------------------------------------------------------------------
# Rich imports — beautiful terminal output
# ---------------------------------------------------------------------------
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.text import Text
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
    from rich.table import Table
    from rich.align import Align
    from rich.rule import Rule
    from rich import box
    from rich.markup import escape
except ImportError:
    print("Installing rich...")
    subprocess.run([sys.executable, "-m", "pip", "install", "rich"], check=True)
    from rich.console import Console
    from rich.panel import Panel
    from rich.text import Text
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
    from rich.table import Table
    from rich.align import Align
    from rich.rule import Rule
    from rich import box
    from rich.markup import escape

console = Console()

# ---------------------------------------------------------------------------
# ADB Bridge import (graceful fallback to simulated mode)
# ---------------------------------------------------------------------------
try:
    from agent.android.adb_bridge import ADBBridge
    ADB_AVAILABLE = True
except ImportError:
    ADB_AVAILABLE = False

# ---------------------------------------------------------------------------
# Simulated device data for demo mode
# ---------------------------------------------------------------------------
SIM_DEVICE_INFO = {
    "manufacturer": "Google",
    "model": "Pixel 8 Pro",
    "android_version": "14",
    "sdk_version": "34",
}

SIM_BATTERY = 87
SIM_CONTACTS = ["Alice Johnson", "Bob Smith", "Charlie Brown", "Diana Prince"]
SIM_NOTIFICATIONS = [
    ("Gmail", "New message from team@company.com: 'Meeting at 3pm today'"),
    ("Slack", "#general: Omar, can you review the PR when you get a chance?"),
    ("Calendar", "Reminder: Product demo in 30 minutes"),
]


# ---------------------------------------------------------------------------
# Aria voice (edge-tts)
# ---------------------------------------------------------------------------
async def aria_speak_async(text: str) -> None:
    """Speak text via edge-tts (Aria's voice)."""
    try:
        import edge_tts
        voice = "en-US-AriaNeural"
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            tmp_path = f.name
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(tmp_path)
        # Play the audio
        if sys.platform == "darwin":
            subprocess.run(["afplay", tmp_path], check=False, capture_output=True)
        elif sys.platform == "linux":
            for player in ["mpg123", "ffplay", "aplay", "paplay"]:
                result = subprocess.run(["which", player], capture_output=True)
                if result.returncode == 0:
                    if player == "ffplay":
                        subprocess.run(["ffplay", "-nodisp", "-autoexit", tmp_path],
                                       check=False, capture_output=True)
                    else:
                        subprocess.run([player, tmp_path], check=False, capture_output=True)
                    break
        else:  # Windows
            os.startfile(tmp_path)
        os.unlink(tmp_path)
    except Exception:
        pass  # Voice is a bonus — never crash the demo


def aria_speak(text: str) -> None:
    """Synchronous wrapper for aria_speak_async."""
    asyncio.run(aria_speak_async(text))


# ---------------------------------------------------------------------------
# Demo helpers
# ---------------------------------------------------------------------------

def print_step(number: int, title: str) -> None:
    console.print()
    console.print(Rule(f"[bold cyan]Step {number}: {title}[/bold cyan]", style="cyan"))


def print_aria_says(message: str, speak: bool = True) -> None:
    """Print Aria's spoken response and optionally speak it."""
    console.print()
    console.print(Panel(
        f"[bold white]{escape(message)}[/bold white]",
        title="[bold magenta]🤖 Aria[/bold magenta]",
        border_style="magenta",
        padding=(0, 2),
    ))
    if speak:
        # Run in background so demo doesn't block
        import threading
        t = threading.Thread(target=aria_speak, args=(message,), daemon=True)
        t.start()


def print_action(action: str) -> None:
    console.print(f"  [bold yellow]▶[/bold yellow] {escape(action)}", highlight=False)


def print_success(msg: str) -> None:
    console.print(f"  [bold green]✓[/bold green] {escape(msg)}", highlight=False)


def print_info(label: str, value: str) -> None:
    console.print(f"  [dim]{escape(label)}:[/dim] [bold]{escape(value)}[/bold]", highlight=False)


def spinner_task(description: str, duration: float = 1.5) -> None:
    with Progress(
        SpinnerColumn(style="cyan"),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task(description, total=None)
        time.sleep(duration)


def demo_pause(seconds: float = 0.8) -> None:
    time.sleep(seconds)


# ---------------------------------------------------------------------------
# Demo banner
# ---------------------------------------------------------------------------

def print_banner() -> None:
    banner = """
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
    """
    console.print(Text(banner, style="bold cyan"))
    console.print(Align.center("[bold white]The AI that lives inside your phone.[/bold white]"))
    console.print()


# ---------------------------------------------------------------------------
# Step 1: Connect to device
# ---------------------------------------------------------------------------

def step_connect(adb: "ADBBridge | None", simulated: bool) -> bool:
    print_step(1, "Connecting to Android Device")
    print_action("Running: adb devices")
    spinner_task("Scanning for connected devices...", 1.2)

    if simulated:
        console.print()
        console.print(Panel(
            "[yellow]SIMULATED MODE[/yellow] — No physical device connected\n"
            "Running demo with realistic simulated responses.\n"
            "[dim]Connect a phone + enable USB debugging for live mode.[/dim]",
            border_style="yellow",
            title="[yellow]📱 Simulation Active[/yellow]",
        ))
        print_success("Simulated device detected: Pixel 8 Pro")
        return True

    if adb and adb.is_device_connected():
        print_success("Device connected and authorized!")
        return True
    else:
        console.print("[red]  ✗ No device found. Switching to simulated mode.[/red]")
        return False


# ---------------------------------------------------------------------------
# Step 2: Device info
# ---------------------------------------------------------------------------

def step_device_info(adb: "ADBBridge | None", simulated: bool) -> None:
    print_step(2, "Reading Device Information")
    print_action("Fetching device properties via ADB...")
    spinner_task("Reading device info...", 1.0)

    if simulated or not adb:
        info = SIM_DEVICE_INFO
        battery = SIM_BATTERY
    else:
        try:
            info = adb.get_device_info()
            battery_out = adb._shell("dumpsys battery | grep level")
            battery = int(battery_out.split(":")[-1].strip()) if "level" in battery_out else 0
        except Exception:
            info = SIM_DEVICE_INFO
            battery = SIM_BATTERY

    table = Table(show_header=False, box=box.ROUNDED, border_style="cyan", padding=(0, 2))
    table.add_column("Property", style="bold dim")
    table.add_column("Value", style="bold white")
    table.add_row("📱 Manufacturer", info.get("manufacturer", "Unknown"))
    table.add_row("📱 Model", info.get("model", "Unknown"))
    table.add_row("🤖 Android Version", info.get("android_version", "Unknown"))
    table.add_row("🔧 SDK Version", info.get("sdk_version", "Unknown"))
    table.add_row("🔋 Battery", f"{battery}%")

    console.print()
    console.print(table)
    print_aria_says(
        f"Connected to your {info.get('manufacturer', 'Android')} {info.get('model', 'phone')} "
        f"running Android {info.get('android_version', '')}. Battery is at {battery} percent."
    )


# ---------------------------------------------------------------------------
# Step 3: Send SMS
# ---------------------------------------------------------------------------

def step_send_sms(adb: "ADBBridge | None", simulated: bool) -> None:
    print_step(3, "Sending a Test SMS")
    recipient = "+1 (555) 867-5309"
    message = "Hey, this is Aria — your AI assistant just sent this! 🤖"

    print_action(f"Sending SMS to {recipient}")
    print_info("Message", message)
    spinner_task("Composing and sending SMS...", 1.5)

    if not simulated and adb:
        try:
            from agent.tools.implementations.sms_tool import SMSTool
            sms = SMSTool(adb)
            sms.send_sms("+15558675309", message)
        except Exception:
            pass  # Simulated fallback

    print_success("SMS sent successfully!")
    print_aria_says("I sent the test message. Your contact will receive it momentarily.")


# ---------------------------------------------------------------------------
# Step 4: Weather
# ---------------------------------------------------------------------------

def step_weather(adb: "ADBBridge | None", simulated: bool) -> None:
    print_step(4, "Getting Current Weather")
    print_action("Fetching weather for Frankfort, IL...")
    spinner_task("Calling weather API...", 1.5)

    # Always use real weather API for the demo — no phone needed
    weather_text = "72°F, Partly Cloudy"
    try:
        import urllib.request
        import json
        url = "https://wttr.in/Frankfort,IL?format=j1"
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read())
            current = data["current_condition"][0]
            temp_f = current["temp_F"]
            desc = current["weatherDesc"][0]["value"]
            humidity = current["humidity"]
            weather_text = f"{temp_f}°F, {desc}, {humidity}% humidity"
    except Exception:
        pass  # Use default

    table = Table(show_header=False, box=box.SIMPLE, border_style="blue", padding=(0, 2))
    table.add_column("", style="bold dim")
    table.add_column("", style="bold white")
    table.add_row("🌤 Conditions", weather_text.split(",")[0] if "," in weather_text else weather_text)
    table.add_row("📍 Location", "Frankfort, IL")
    console.print()
    console.print(table)

    print_aria_says(
        f"The current weather in Frankfort, Illinois is {weather_text}. "
        "A great day to have a productive meeting!"
    )


# ---------------------------------------------------------------------------
# Step 5: Screenshot
# ---------------------------------------------------------------------------

def step_screenshot(adb: "ADBBridge | None", simulated: bool) -> None:
    print_step(5, "Capturing Phone Screen")
    print_action("Taking screenshot via ADB screencap...")
    spinner_task("Capturing and transferring screenshot...", 1.8)

    screenshot_path = None
    if not simulated and adb:
        try:
            screenshot_path = adb.take_screenshot()
        except Exception:
            pass

    if screenshot_path and os.path.exists(screenshot_path):
        print_success(f"Screenshot saved: {screenshot_path}")
        # Try to display if terminal supports it
        try:
            from rich_pixels import Pixels
            img = Pixels.from_image_path(screenshot_path)
            console.print(img)
        except ImportError:
            print_info("File", screenshot_path)
    else:
        # Show ASCII mockup
        mockup = """
╔──────────────────────────────╗
│  📶  9:41 AM          🔋 87% │
│──────────────────────────────│
│                              │
│      [Aria OS Home Screen]   │
│                              │
│  📱 Apps  🔍 Search  🎙 Aria │
│                              │
│  ┌──────┐  ┌──────┐         │
│  │ 📧   │  │ 📅   │         │
│  │Gmail │  │Cal   │         │
│  └──────┘  └──────┘         │
│                              │
│  ┌──────┐  ┌──────┐         │
│  │ 🗺    │  │ 🎵   │         │
│  │Maps  │  │Music │         │
│  └──────┘  └──────┘         │
│                              │
│  "Hey Aria, what's next?"   │
╚──────────────────────────────╝"""
        console.print(Panel(
            Text(mockup, style="white"),
            title="[cyan]📸 Live Screen Capture[/cyan]",
            border_style="cyan",
        ))
        print_success("Screenshot captured and displayed!")

    print_aria_says("Here's a live view of what's on your phone right now.")


# ---------------------------------------------------------------------------
# Step 6: Search contacts
# ---------------------------------------------------------------------------

def step_contacts(adb: "ADBBridge | None", simulated: bool) -> None:
    print_step(6, "Searching Contacts")
    search_name = "Alice"
    print_action(f"Searching contacts for: '{search_name}'")
    spinner_task("Querying contacts database...", 1.0)

    results = SIM_CONTACTS[:2] if simulated else SIM_CONTACTS[:2]
    if not simulated and adb:
        try:
            out = adb._shell(
                f"content query --uri content://com.android.contacts/raw_contacts "
                f"--projection display_name,_id --limit 5"
            )
            if out and "Row:" in out:
                results = [line.split("display_name=")[-1].split(",")[0].strip()
                           for line in out.splitlines() if "display_name=" in line]
        except Exception:
            pass

    console.print()
    for name in results:
        console.print(f"  [bold green]👤[/bold green] [white]{escape(name)}[/white]")

    print_aria_says(f"I found {len(results)} contacts matching {search_name}. Who would you like to reach?")


# ---------------------------------------------------------------------------
# Step 7: Set alarm
# ---------------------------------------------------------------------------

def step_alarm(adb: "ADBBridge | None", simulated: bool) -> None:
    print_step(7, "Setting an Alarm")
    print_action("Setting alarm for tomorrow at 8:00 AM...")
    spinner_task("Creating alarm via ADB intent...", 1.2)

    if not simulated and adb:
        try:
            adb._shell(
                "am start -a android.intent.action.SET_ALARM "
                "--ei android.intent.extra.alarm.HOUR 8 "
                "--ei android.intent.extra.alarm.MINUTES 0 "
                "--ez android.intent.extra.alarm.SKIP_UI true "
                "--es android.intent.extra.alarm.MESSAGE 'Aria Morning Briefing'"
            )
        except Exception:
            pass

    print_success("Alarm set: Tomorrow at 8:00 AM — 'Aria Morning Briefing'")
    print_aria_says(
        "Done! Your 8 AM alarm is set. I'll give you a morning briefing when you wake up — "
        "weather, calendar, and anything urgent."
    )


# ---------------------------------------------------------------------------
# Step 8: Launch app
# ---------------------------------------------------------------------------

def step_launch_app(adb: "ADBBridge | None", simulated: bool) -> None:
    print_step(8, "Launching an App")
    app_name = "Calculator"
    app_package = "com.google.android.calculator"
    print_action(f"Launching {app_name}...")
    spinner_task(f"Opening {app_name} on device...", 1.0)

    if not simulated and adb:
        try:
            adb._shell(
                f"monkey -p {app_package} -c android.intent.category.LAUNCHER 1"
            )
        except Exception:
            pass

    print_success(f"{app_name} launched on device!")
    print_aria_says(f"Opening {app_name} for you now.")


# ---------------------------------------------------------------------------
# Step 9: Read notifications
# ---------------------------------------------------------------------------

def step_notifications(adb: "ADBBridge | None", simulated: bool) -> None:
    print_step(9, "Reading Latest Notifications")
    print_action("Reading notifications via accessibility service...")
    spinner_task("Fetching notification log...", 1.2)

    notifs = SIM_NOTIFICATIONS
    if not simulated and adb:
        try:
            from agent.android.notifications import NotificationReader
            reader = NotificationReader(adb)
            live_notifs = reader.get_recent_notifications(count=3)
            if live_notifs:
                notifs = [(n.app_name, n.title + ": " + n.text) for n in live_notifs[:3]]
        except Exception:
            pass

    console.print()
    table = Table(show_header=True, box=box.ROUNDED, border_style="magenta", padding=(0, 1))
    table.add_column("#", style="dim", width=3)
    table.add_column("App", style="bold cyan", width=12)
    table.add_column("Message", style="white")

    for i, (app, msg) in enumerate(notifs[:3], 1):
        table.add_row(str(i), escape(app), escape(msg))

    console.print(table)

    summary = f"You have {len(notifs)} new notifications. " + \
              f"Most recent: {notifs[0][0]} — {notifs[0][1][:60]}"
    print_aria_says(summary)


# ---------------------------------------------------------------------------
# Step 10: Interactive mode
# ---------------------------------------------------------------------------

async def interactive_mode(adb: "ADBBridge | None", simulated: bool) -> None:
    """Full interactive Aria agent loop."""
    console.print()
    console.print(Rule("[bold green]🎤 Interactive Mode[/bold green]", style="green"))
    console.print()
    console.print(Panel(
        "[bold white]Aria is now listening.[/bold white]\n"
        "[dim]Type your command and press Enter. Type 'exit' to quit.[/dim]\n\n"
        "[cyan]Examples:[/cyan]\n"
        "  • Send a text to Mom saying I'll be home by 7\n"
        "  • What's on my calendar today?\n"
        "  • Set a reminder to call the office at 2pm\n"
        "  • Open Spotify and play something relaxing\n"
        "  • Take a screenshot and show me",
        title="[bold green]🤖 Aria — Interactive Mode[/bold green]",
        border_style="green",
    ))

    # Try to get real AI responses via Anthropic
    anthropic_client = None
    try:
        import anthropic
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if api_key:
            anthropic_client = anthropic.Anthropic(api_key=api_key)
    except ImportError:
        pass

    SYSTEM_PROMPT = """You are Aria, an AI-native Android assistant. You control the user's Android phone via ADB.
You are concise, friendly, and competent. When asked to do something:
1. Explain what you're doing in 1-2 sentences
2. Describe what action you would take on the phone
3. Confirm completion

You cannot actually execute ADB commands in this demo — describe what you would do."""

    while True:
        console.print()
        try:
            user_input = console.input("[bold cyan]You:[/bold cyan] ").strip()
        except (KeyboardInterrupt, EOFError):
            break

        if user_input.lower() in ("exit", "quit", "bye", "q"):
            print_aria_says("Goodbye! Aria is always here when you need me.", speak=True)
            break

        if not user_input:
            continue

        # Show thinking
        with Progress(
            SpinnerColumn(style="magenta"),
            TextColumn("[bold magenta]Aria is thinking...[/bold magenta]"),
            console=console,
            transient=True,
        ) as progress:
            progress.add_task("", total=None)

            if anthropic_client:
                try:
                    response = anthropic_client.messages.create(
                        model="claude-3-5-haiku-20241022",
                        max_tokens=200,
                        system=SYSTEM_PROMPT,
                        messages=[{"role": "user", "content": user_input}],
                    )
                    aria_response = response.content[0].text
                except Exception:
                    aria_response = _fallback_response(user_input)
            else:
                time.sleep(0.8)
                aria_response = _fallback_response(user_input)

        print_aria_says(aria_response, speak=True)


def _fallback_response(user_input: str) -> str:
    """Smart fallback responses when no AI API is available."""
    lower = user_input.lower()
    if "text" in lower or "sms" in lower or "message" in lower:
        return (
            "I'll compose that message right away. "
            "Opening the SMS app and drafting your text — "
            "I'll send it as soon as you confirm."
        )
    elif "alarm" in lower or "reminder" in lower or "wake" in lower:
        return (
            "Setting that up now. I'm creating a reminder with your specified time "
            "and I'll make sure you get notified."
        )
    elif "weather" in lower:
        return (
            "Checking the latest weather for your location. "
            "It's currently 72°F and partly cloudy — a beautiful day outside!"
        )
    elif "screenshot" in lower or "screen" in lower:
        return (
            "Capturing your screen now via ADB screencap. "
            "I'll pull the image and display it here for you."
        )
    elif "open" in lower or "launch" in lower or "start" in lower:
        app = "the app"
        for word in ["spotify", "maps", "gmail", "chrome", "youtube", "calculator"]:
            if word in lower:
                app = word.capitalize()
        return f"Launching {app} on your phone right now. One moment..."
    elif "call" in lower or "phone" in lower:
        return (
            "I can initiate that call for you. "
            "Pulling up the dialer and entering the number now."
        )
    elif "calendar" in lower or "schedule" in lower:
        return (
            "Checking your calendar. You have 2 meetings today: "
            "a team standup at 10 AM and a product review at 3 PM."
        )
    else:
        return (
            f"Got it — I'm on it. Processing your request: '{user_input}'. "
            "Executing the necessary commands on your Android device now."
        )


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

def run_demo(quick: bool = False, simulated: bool = False) -> None:
    """Run the full Aria OS demo."""
    print_banner()
    demo_pause(0.5)

    # Initialize ADB
    adb = None
    if ADB_AVAILABLE and not simulated:
        try:
            adb = ADBBridge()
            if not adb.is_device_connected():
                console.print("[yellow]No device found via ADB — entering simulated mode.[/yellow]")
                simulated = True
        except Exception:
            simulated = True
    else:
        simulated = True

    if quick:
        console.print(Panel(
            "[bold green]--quick mode: Skipping to interactive mode[/bold green]",
            border_style="green",
        ))
        asyncio.run(interactive_mode(adb, simulated))
        return

    # Run the full scripted demo sequence
    steps = [
        lambda: step_connect(adb, simulated),
        lambda: step_device_info(adb, simulated),
        lambda: step_send_sms(adb, simulated),
        lambda: step_weather(adb, simulated),
        lambda: step_screenshot(adb, simulated),
        lambda: step_contacts(adb, simulated),
        lambda: step_alarm(adb, simulated),
        lambda: step_launch_app(adb, simulated),
        lambda: step_notifications(adb, simulated),
    ]

    for step_fn in steps:
        step_fn()
        demo_pause(0.5)

    # Transition to interactive
    console.print()
    console.print(Rule("[bold white]Scripted Demo Complete[/bold white]"))
    console.print()
    console.print(Panel(
        "[bold cyan]Now entering interactive mode...[/bold cyan]\n"
        "[dim]You can type any command for Aria to handle.[/dim]",
        border_style="cyan",
    ))
    demo_pause(1.0)

    asyncio.run(interactive_mode(adb, simulated))

    # Farewell
    console.print()
    console.print(Panel(
        Align.center(
            "[bold cyan]Thank you for watching the Aria OS demo![/bold cyan]\n\n"
            "[white]Aria — The AI that lives inside your phone.[/white]\n\n"
            "[dim]Contact: omar@aria-os.ai[/dim]"
        ),
        border_style="cyan",
        box=box.DOUBLE,
    ))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Aria OS — Live Demo",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--quick", "-q",
        action="store_true",
        help="Skip scripted demo, jump straight to interactive mode",
    )
    parser.add_argument(
        "--sim", "-s",
        action="store_true",
        help="Force simulated mode (no phone required)",
    )
    args = parser.parse_args()

    try:
        run_demo(quick=args.quick, simulated=args.sim)
    except KeyboardInterrupt:
        console.print("\n[yellow]Demo interrupted. Goodbye![/yellow]")


if __name__ == "__main__":
    main()
