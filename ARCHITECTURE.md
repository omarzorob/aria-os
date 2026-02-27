# Aria OS — Architecture

## System Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Android Device                              │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                     Flutter UI (Dart)                        │  │
│  │   ChatScreen  │  VoiceScreen  │  SettingsScreen              │  │
│  └────────────────────────┬─────────────────────────────────────┘  │
│                           │  MethodChannel (ai.aria.os/agent)       │
│  ┌────────────────────────▼─────────────────────────────────────┐  │
│  │               MainActivity.kt (FlutterActivity)              │  │
│  └────────────────────────┬─────────────────────────────────────┘  │
│                           │  startService(Intent)                   │
│  ┌────────────────────────▼─────────────────────────────────────┐  │
│  │            AriaAgentService.kt (Foreground Service)          │  │
│  │                                                              │  │
│  │   ┌──────────────┐    ┌──────────────┐   ┌──────────────┐   │  │
│  │   │ContextManager│    │  TaskPlanner │   │ToolRegistry  │   │  │
│  │   └──────────────┘    └──────────────┘   └──────┬───────┘   │  │
│  │                                                  │           │  │
│  │   ┌───────────────────────────────────────────┐  │           │  │
│  │   │           ClaudeClient.kt                 │  │           │  │
│  │   │   POST /v1/messages  (OkHttp, HTTPS)      │  │           │  │
│  │   └────────────────────┬──────────────────────┘  │           │  │
│  └────────────────────────│──────────────────────────│───────────┘  │
│                           │ HTTPS                    │ Tool call     │
│  ┌────────────────────────▼──────────┐   ┌──────────▼───────────┐  │
│  │         Anthropic Claude API      │   │  Android Tool Layer  │  │
│  │  claude-3-5-haiku-20241022        │   │  SMS / Contacts /    │  │
│  │  Tool schemas → tool_use response │   │  Calendar / Maps /   │  │
│  └───────────────────────────────────┘   │  Settings / etc.     │  │
│                                          └──────────────────────┘  │
│                                                                     │
│  ┌──────────────────────┐   ┌──────────────────────────────────┐   │
│  │ AriaAccessibility    │   │  AriaVoice + WakeWordDetector    │   │
│  │ Service.kt           │   │  SpeechRecognizer + TTS          │   │
│  │ Reads/controls any   │   │  "Hey Aria" → listen → speak    │   │
│  │ app on screen        │   └──────────────────────────────────┘   │
│  └──────────────────────┘                                          │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                 Room Database (SQLite)                       │  │
│  │          ConversationMessages  │  MemoryFacts               │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Components

### Flutter UI (`aria-app/lib/`)

Pure presentation layer. Written in Dart. Compiled to native ARM code by Flutter.

- **ChatScreen** — Scrollable message list. Bottom input bar. Sends via `AriaChannel.sendMessage()`.
- **VoiceScreen** — Full-screen animated voice mode. Shows state: Listening / Thinking / Speaking.
- **SettingsScreen** — API key config, toggle wake word, toggle voice response, accessibility shortcut.

Communication to Kotlin: `MethodChannel('ai.aria.os/agent')`  
Communication from Kotlin: `EventChannel` or local `BroadcastReceiver` → `MethodChannel` callback.

### MainActivity.kt

Bridges Flutter and Android. Sets up the `MethodChannel` handler. Starts `AriaAgentService` on launch.

### AriaAgentService.kt

The heart of Aria. A `LifecycleService` (foreground service) that:

1. Maintains a persistent `conversationHistory: List<Message>`
2. Receives user messages via `Intent("SEND_MESSAGE")`
3. Calls `ClaudeClient.chat()` with conversation + tool schemas
4. Parses `tool_use` blocks from response
5. Dispatches tool calls to `ToolRegistry`
6. Appends tool results back to conversation
7. Broadcasts final `text` reply via `Intent("ai.aria.os.REPLY")`
8. Calls `AriaVoice.speak(reply)`

Runs as `START_STICKY` — Android restarts it if killed.

### ClaudeClient.kt

OkHttp-based HTTPS client. Serializes `List<Message>` + tool schemas to Anthropic's Messages API format.

```
POST https://api.anthropic.com/v1/messages
Headers:
  x-api-key: <CLAUDE_API_KEY>
  anthropic-version: 2023-06-01
  content-type: application/json

Body:
{
  "model": "claude-3-5-haiku-20241022",
  "max_tokens": 1024,
  "system": "...",
  "messages": [...],
  "tools": [...]
}
```

Response parsing: iterates `content[]` blocks, extracts `text` and `tool_use` blocks.

### ToolRegistry.kt

Maps tool names (`String`) → `AriaTool` instances. Generates tool schemas for Claude.

### AriaTool (base class)

```kotlin
abstract class AriaTool {
    abstract val description: String
    abstract val inputSchema: Map<String, Any>   // JSON Schema object
    abstract suspend fun execute(input: Map<String, Any>): String
}
```

All tools are coroutine-safe (`suspend fun`). Results are returned as plain text or JSON strings.

---

## Accessibility Service Integration

`AriaAccessibilityService` extends Android's `AccessibilityService`. Once enabled by the user:

- `onServiceConnected()` → stores `instance` in companion object
- `getScreenText()` → walks the view tree and concatenates all visible text
- `tapAt(x, y)` → dispatches a gesture to tap a coordinate
- `swipe(x1,y1,x2,y2)` → dispatches a swipe gesture
- `pressBack()` / `pressHome()` → global actions

Tools or `AriaAgentService` can call `AriaAccessibilityService.instance?.getScreenText()` to read context.

---

## Voice Pipeline

```
SpeechRecognizer  →  WakeWordDetector  →  AriaAgentService
                                               ↓
                                         ClaudeClient
                                               ↓
                                         AriaVoice.speak()
```

1. `WakeWordDetector` runs continuous recognition loop
2. On "hey aria" or "aria" match → calls `onWakeWordDetected()`
3. `AriaAgentService` switches to full recognition mode
4. Recognized text → `handleUserMessage(text)`
5. Response text → `AriaVoice.speak(reply)`

---

## Tool Registration & Dispatch

```kotlin
// Registration (ToolRegistry)
val tools = mapOf(
    "send_sms" to SmsTool(context),
    ...
)

// Schema generation
tools.map { (name, tool) ->
    mapOf("name" to name, "description" to tool.description, "input_schema" to tool.inputSchema)
}

// Dispatch (AriaAgentService)
response.toolCalls.forEach { toolCall ->
    val result = toolRegistry.getTool(toolCall.name)?.execute(toolCall.input)
    conversationHistory.add(Message("tool", result, toolCall.id))
}
```

---

## Data Flow: End-to-End

```
User types "Send a text to Mom saying I'm on my way"
    │
    ▼
ChatScreen.onSend()
    │ MethodChannel.invokeMethod("sendMessage", ...)
    ▼
MainActivity.setMethodCallHandler
    │ startService(Intent("SEND_MESSAGE"))
    ▼
AriaAgentService.handleUserMessage(text)
    │ conversationHistory.add(Message("user", text))
    │ claudeClient.chat(history, toolSchemas, systemPrompt)
    ▼
Claude API → returns tool_use: { name: "send_sms", input: { to: "Mom", message: "I'm on my way" } }
    │
    ▼
ToolRegistry.getTool("send_sms") → SmsTool
    │ SmsTool.execute({ to: "Mom", message: "..." })
    │   → ContactsTool resolves "Mom" → phone number
    │   → SmsManager.sendTextMessage(number, null, message, ...)
    │   → returns "SMS sent to +1-555-0100"
    ▼
conversationHistory.add(Message("tool", "SMS sent to +1-555-0100", toolCallId))
    │ claudeClient.chat(history, ...) — second turn
    ▼
Claude API → returns text: "Done! Sent your mom a text."
    │
    ▼
broadcastReply("Done! Sent your mom a text.")
    │ sendBroadcast(Intent("ai.aria.os.REPLY"))
    ▼
ChatScreen BroadcastReceiver → adds message bubble
    │
    ▼
AriaVoice.speak("Done! Sent your mom a text.")
```

---

## Memory (Room Database)

Two tables:
- `conversation_messages` — rolling chat history (id, role, content, timestamp)
- `memory_facts` — persistent key/value facts Aria learns about the user

Both are accessed via Kotlin coroutines (`lifecycleScope.launch`).

---

## IPC Summary

| Direction | Mechanism |
|-----------|-----------|
| Flutter → Kotlin | `MethodChannel` invoke |
| Kotlin → Flutter | `BroadcastReceiver` → EventChannel or MethodChannel callback |
| Activity → Service | `startService(Intent)` |
| Service → UI | `sendBroadcast(Intent("ai.aria.os.REPLY"))` |
| Boot → Service | `BroadcastReceiver(BOOT_COMPLETED)` → `startForegroundService` |
