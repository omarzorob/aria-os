"""
Aria Agent Core — Phase 1 scaffold
Runs on any Android device via ADB + Accessibility Service
"""

import anthropic
import json
import subprocess
from pathlib import Path

# Tools Aria can use
TOOLS = [
    {
        "name": "send_sms",
        "description": "Send a text message to a contact",
        "input_schema": {
            "type": "object",
            "properties": {
                "contact": {"type": "string", "description": "Name or phone number"},
                "message": {"type": "string", "description": "Message to send"}
            },
            "required": ["contact", "message"]
        }
    },
    {
        "name": "send_email",
        "description": "Send an email",
        "input_schema": {
            "type": "object",
            "properties": {
                "to": {"type": "string"},
                "subject": {"type": "string"},
                "body": {"type": "string"}
            },
            "required": ["to", "subject", "body"]
        }
    },
    {
        "name": "make_call",
        "description": "Make a phone call",
        "input_schema": {
            "type": "object",
            "properties": {
                "contact": {"type": "string"}
            },
            "required": ["contact"]
        }
    },
    {
        "name": "open_app",
        "description": "Open an app by name",
        "input_schema": {
            "type": "object",
            "properties": {
                "app_name": {"type": "string"}
            },
            "required": ["app_name"]
        }
    },
    {
        "name": "tap_screen",
        "description": "Tap a UI element on screen by description",
        "input_schema": {
            "type": "object",
            "properties": {
                "element": {"type": "string", "description": "Text or description of element to tap"}
            },
            "required": ["element"]
        }
    },
    {
        "name": "web_search",
        "description": "Search the web and return results",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "set_reminder",
        "description": "Set a reminder or alarm",
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "time": {"type": "string", "description": "Natural language time (e.g. '3pm', 'in 20 minutes')"}
            },
            "required": ["text", "time"]
        }
    },
    {
        "name": "order_food",
        "description": "Order food via UberEats or DoorDash",
        "input_schema": {
            "type": "object",
            "properties": {
                "restaurant": {"type": "string"},
                "items": {"type": "string", "description": "What to order"}
            },
            "required": ["restaurant"]
        }
    }
]

SYSTEM_PROMPT = """You are Aria, an AI assistant built into the user's phone.
You have deep access to the phone — you can send messages, make calls, open apps,
tap the screen, search the web, set reminders, and order things.

Be direct and efficient. Confirm before taking irreversible actions (sending messages, 
making purchases). For research tasks, be thorough. Remember context across the conversation.

You are not a chatbot — you are an operator. Your job is to get things done."""


class AriaAgent:
    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.history = []

    def run(self, user_input: str) -> str:
        self.history.append({"role": "user", "content": user_input})

        response = self.client.messages.create(
            model="claude-opus-4-6",
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=self.history
        )

        # Handle tool calls
        while response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result = self._execute_tool(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result
                    })

            self.history.append({"role": "assistant", "content": response.content})
            self.history.append({"role": "user", "content": tool_results})

            response = self.client.messages.create(
                model="claude-opus-4-6",
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                tools=TOOLS,
                messages=self.history
            )

        reply = next(b.text for b in response.content if hasattr(b, "text"))
        self.history.append({"role": "assistant", "content": reply})
        return reply

    def _execute_tool(self, tool_name: str, inputs: dict) -> str:
        """Execute a tool — stub implementations for Phase 1."""
        print(f"[TOOL] {tool_name}({inputs})")

        # Phase 1: ADB-based implementations
        if tool_name == "send_sms":
            return self._adb_send_sms(inputs["contact"], inputs["message"])
        elif tool_name == "open_app":
            return self._adb_open_app(inputs["app_name"])
        elif tool_name == "web_search":
            return self._web_search(inputs["query"])
        else:
            return f"[stub] Would execute: {tool_name} with {inputs}"

    def _adb_send_sms(self, contact: str, message: str) -> str:
        """Send SMS via ADB shell."""
        cmd = f'adb shell am start -a android.intent.action.SENDTO -d "sms:{contact}" --es "sms_body" "{message}" --ez "exit_on_sent" true'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return "SMS intent launched" if result.returncode == 0 else f"Error: {result.stderr}"

    def _adb_open_app(self, app_name: str) -> str:
        """Open app via ADB."""
        # Map common names to package names
        packages = {
            "chrome": "com.android.chrome",
            "gmail": "com.google.android.gm",
            "maps": "com.google.android.apps.maps",
            "camera": "com.android.camera2",
            "settings": "com.android.settings",
            "ubereats": "com.ubercab.eats",
        }
        pkg = packages.get(app_name.lower(), f"com.{app_name.lower()}")
        cmd = f"adb shell monkey -p {pkg} -c android.intent.category.LAUNCHER 1"
        subprocess.run(cmd, shell=True)
        return f"Opened {app_name}"

    def _web_search(self, query: str) -> str:
        """Search the web — stub."""
        return f"[stub] Would search: {query}"


if __name__ == "__main__":
    import os
    agent = AriaAgent(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
    print("Aria ready. Type to talk, Ctrl+C to exit.\n")
    while True:
        try:
            user_input = input("You: ").strip()
            if not user_input:
                continue
            response = agent.run(user_input)
            print(f"\nAria: {response}\n")
        except KeyboardInterrupt:
            print("\nBye.")
            break
