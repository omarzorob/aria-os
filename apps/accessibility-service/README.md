# Aria Accessibility Service APK

An Android Accessibility Service that exposes a JSON-RPC socket server on port **7765**, enabling the Aria OS Python agent to read screen content, find UI elements, perform gestures, and type text on the device.

## Architecture

```
┌─────────────────────────────────────────────────┐
│  Android Device                                  │
│                                                  │
│  ┌─────────────────────────────────────┐         │
│  │  AriaAccessibilityService           │         │
│  │  (Android AccessibilityService)     │         │
│  │                                     │         │
│  │  ┌──────────────┐  ┌─────────────┐  │         │
│  │  │ SocketServer │  │CommandHandler│  │         │
│  │  │  port 7765   │──│             │  │         │
│  │  └──────────────┘  └──────┬──────┘  │         │
│  │                           │         │         │
│  │                    ┌──────┴──────┐  │         │
│  │                    │ElementFinder│  │         │
│  │                    └─────────────┘  │         │
│  └─────────────────────────────────────┘         │
│           ▲ TCP port 7765                         │
└───────────┼─────────────────────────────────────-┘
            │ ADB port forward: tcp:7765 → tcp:7765
┌───────────┴──────────────────────────────────────┐
│  Host Machine                                    │
│  Python agent: AccessibilityServiceBridge        │
│  (agent/android/accessibility_service.py)        │
└──────────────────────────────────────────────────┘
```

## Source Files

| File | Description |
|------|-------------|
| `AriaAccessibilityService.kt` | Main Android AccessibilityService — manages lifecycle and exposes gesture/action API |
| `SocketServer.kt` | JSON-RPC TCP server listening on port 7765 |
| `CommandHandler.kt` | Dispatches JSON-RPC commands to the service API |
| `ElementFinder.kt` | Traverses the accessibility node tree to find/list UI elements |

## Build

### Prerequisites

- Android SDK (API 34)
- JDK 17+
- Gradle (wrapper included)

### Compile the APK

```bash
cd apps/accessibility-service
./gradlew assembleDebug
```

The APK will be output to:
```
app/build/outputs/apk/debug/app-debug.apk
```

### Release build

```bash
./gradlew assembleRelease
```

## Install on Device

```bash
adb install app/build/outputs/apk/debug/app-debug.apk
```

Or upgrade an existing installation:
```bash
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

## Enable the Service

1. Open **Settings** on the Android device
2. Go to **Accessibility** → **Downloaded apps** (or **Installed services**)
3. Find **Aria Accessibility Service**
4. Toggle it **ON**
5. Accept the permission prompt

## Set Up ADB Port Forwarding

Before the Python agent can connect, forward the device port to localhost:

```bash
adb forward tcp:7765 tcp:7765
```

To verify the service is running:

```bash
# From the host machine, connect and ping
echo '{"method": "ping", "params": {}}' | nc localhost 7765
# Expected: {"success":true,"result":{"status":"ok","service":"aria-accessibility"}}
```

## Python Agent Connection

The Python bridge at `agent/android/accessibility_service.py` handles the connection:

```python
from agent.android.accessibility_service import AccessibilityServiceBridge

with AccessibilityServiceBridge() as bridge:
    # Check connectivity
    print(bridge.ping())
    # → {"status": "ok", "service": "aria-accessibility"}

    # Get all visible UI elements
    elements = bridge.get_screen_elements()
    for el in elements:
        print(el.text, el.bounds)

    # Find by text
    buttons = bridge.find_element_by_text("Submit")

    # Tap at coordinates
    bridge.tap_coords(540, 1200)

    # Type text into focused field
    bridge.type_text("Hello, World!")

    # Navigate
    bridge.press_back()
    bridge.press_home()

    # Scroll
    bridge.scroll_forward()
```

## JSON-RPC API Reference

All commands follow this format:

**Request:**
```json
{"method": "command_name", "params": {"key": "value"}}
```

**Success Response:**
```json
{"success": true, "result": ...}
```

**Error Response:**
```json
{"success": false, "error": "error message"}
```

### Available Commands

| Method | Params | Returns |
|--------|--------|---------|
| `ping` | — | `{"status": "ok", "service": "aria-accessibility"}` |
| `get_screen_elements` | — | Array of UIElement objects |
| `get_screen_text` | — | `{"text": "all visible text"}` |
| `get_focused_app` | — | `{"package": "com.example.app"}` |
| `find_element_by_text` | `text: string` | Array of UIElement objects |
| `find_element_by_id` | `id: string` | Array of UIElement objects |
| `tap_element` | `nodeId: int` | `{"clicked": bool}` |
| `tap_coords` | `x: float, y: float` | `{"tapped": bool, "x": ..., "y": ...}` |
| `swipe` | `x1, y1, x2, y2: float, duration: long` | `{"swiped": bool}` |
| `type_text` | `text: string` | `{"typed": bool, "text": "..."}` |
| `press_back` | — | `{"action": "back"}` |
| `press_home` | — | `{"action": "home"}` |
| `press_recents` | — | `{"action": "recents"}` |
| `press_notifications` | — | `{"action": "notifications"}` |
| `scroll_forward` | `nodeId?: int` | `{"scrolled": bool, "direction": "forward"}` |
| `scroll_backward` | `nodeId?: int` | `{"scrolled": bool, "direction": "backward"}` |

### UIElement Schema

```json
{
  "id": "com.example:id/button",
  "text": "Submit",
  "contentDescription": "Submit button",
  "className": "android.widget.Button",
  "bounds": {"left": 100, "top": 200, "right": 300, "bottom": 250},
  "isClickable": true,
  "isEditable": false,
  "isScrollable": false,
  "isEnabled": true,
  "childCount": 0,
  "nodeHashCode": 123456789
}
```

## Troubleshooting

**Service not appearing in Accessibility settings:**
- Make sure the APK is installed: `adb shell pm list packages | grep aria`
- Check the manifest has the correct intent-filter

**Connection refused on port 7765:**
- Verify the service is enabled in Accessibility settings
- Re-run `adb forward tcp:7765 tcp:7765`
- Check logcat: `adb logcat -s AriaService AriaSocketServer`

**Elements not found:**
- The service needs `canRetrieveWindowContent="true"` — check the XML config
- Some apps block accessibility services (banking apps, etc.)

**Gestures not working:**
- The service needs `canPerformGestures="true"` — check the XML config
- Some devices require the service to be enabled with full permissions
