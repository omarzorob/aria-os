"""
P2-11: Aria OS — Main Agent Entry Point

Ties everything together:
  - Loads all tools via ToolLoader
  - Initialises session memory
  - Connects to ADB device via ADBManager
  - Starts the FastAPI server

Run directly:
    python -m agent.main_agent
    # or
    python agent/main_agent.py

Environment variables:
    ANTHROPIC_API_KEY   — Anthropic API key (preferred)
    OPENAI_API_KEY      — OpenAI API key (fallback)
    ARIA_HOST           — Server bind host (default: 0.0.0.0)
    ARIA_PORT           — Server port (default: 8765)
    ARIA_MEMORY_PATH    — Path to persist session memory (default: memory/session.json)
    ARIA_ADB_SERIAL     — Target Android device serial (optional)
    ARIA_LOG_LEVEL      — Logging level: DEBUG/INFO/WARNING (default: INFO)
"""

from __future__ import annotations

import logging
import os
import signal
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Setup logging
# ---------------------------------------------------------------------------


def setup_logging(level: str = "INFO") -> None:
    """Configure root logger with a readable format."""
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )


# ---------------------------------------------------------------------------
# Initialise subsystems
# ---------------------------------------------------------------------------


def init_adb_manager() -> "ADBManager | None":
    """
    Initialise the ADB device manager and optionally select a specific device.

    Returns:
        ADBManager instance, or None if adb is not available.
    """
    try:
        from agent.android.adb_manager import ADBManager

        manager = ADBManager()
        serial = os.environ.get("ARIA_ADB_SERIAL", "")
        if serial:
            try:
                manager.select_device(serial)
                logger.info("ADB device selected: %s", serial)
            except ValueError as exc:
                logger.warning("Could not select ADB device %s: %s", serial, exc)

        # Start auto-reconnect in background
        manager.auto_reconnect(interval=10)

        # Event hooks for logging
        manager.on_connect(lambda d: logger.info("📱 Device connected: %s", d))
        manager.on_disconnect(lambda d: logger.warning("📵 Device disconnected: %s", d))

        return manager

    except Exception as exc:
        logger.warning("ADB manager init failed (continuing without device): %s", exc)
        return None


def init_tool_registry(adb_bridge=None) -> "ToolRegistry | None":
    """
    Discover and register all tools from agent/tools/implementations/.

    Args:
        adb_bridge: ADBBridge instance to pass to tools.

    Returns:
        ToolRegistry with all tools loaded, or None on failure.
    """
    try:
        from agent import tool_registry
        from agent.tool_loader import register_all, scan_tools

        classes = scan_tools()
        logger.info("Discovered %d tool class(es)", len(classes))

        registered = register_all(tool_registry, adb_bridge)
        logger.info("Registered %d tool(s)", registered)

        return tool_registry

    except Exception as exc:
        logger.error("Tool registry init failed: %s", exc)
        return None


def init_session_memory(memory_path: str | None = None) -> "SessionMemory":
    """
    Initialise session memory, loading from disk if a saved session exists.

    Args:
        memory_path: Path to session JSON file. Defaults to ARIA_MEMORY_PATH env var.

    Returns:
        SessionMemory instance.
    """
    from agent.memory.session import SessionMemory

    mem = SessionMemory()
    path = memory_path or os.environ.get("ARIA_MEMORY_PATH", "memory/session.json")
    session_file = Path(path)

    if session_file.exists():
        try:
            mem.load(session_file)
            logger.info("Session memory loaded (%d messages)", mem.message_count)
        except Exception as exc:
            logger.warning("Could not load session memory from %s: %s", session_file, exc)
    else:
        logger.info("Starting fresh session (no saved memory at %s)", session_file)

    return mem


def print_banner(adb_manager=None, tool_registry=None) -> None:
    """Print a startup banner with system status."""
    tool_count = 0
    if tool_registry is not None:
        try:
            from agent.tool_registry import all_tools
            tool_count = len(all_tools())
        except Exception:
            pass

    device_info = "not connected"
    if adb_manager is not None:
        try:
            devices = adb_manager.list_devices()
            online = [d for d in devices if d.is_online]
            if online:
                d = online[0]
                device_info = f"{d.model} (Android {d.android_version})"
        except Exception:
            pass

    host = os.environ.get("ARIA_HOST", "0.0.0.0")
    port = os.environ.get("ARIA_PORT", "8765")

    print()
    print("  ╔══════════════════════════════════════════════╗")
    print("  ║           A R I A  O S  —  v1.0.0           ║")
    print("  ║       AI-native Android OS Agent             ║")
    print("  ╠══════════════════════════════════════════════╣")
    print(f"  ║  Server  : http://{host}:{port:<26}║")
    print(f"  ║  Tools   : {tool_count:<35} ║")
    print(f"  ║  Device  : {device_info:<35} ║")
    print("  ╚══════════════════════════════════════════════╝")
    print()


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """
    Main entry point — initialises all subsystems and starts the HTTP server.

    This function blocks until the server is stopped (Ctrl-C or SIGTERM).
    """
    # Setup logging first
    log_level = os.environ.get("ARIA_LOG_LEVEL", "INFO")
    setup_logging(log_level)

    logger.info("Aria OS agent starting up…")

    # -----------------------------------------------------------------------
    # 1. ADB Device Manager
    # -----------------------------------------------------------------------
    adb_manager = init_adb_manager()
    adb_bridge = None
    if adb_manager is not None:
        try:
            adb_bridge = adb_manager.get_device()
        except Exception as exc:
            logger.warning("No Android device available: %s", exc)

    # -----------------------------------------------------------------------
    # 2. Tool Registry
    # -----------------------------------------------------------------------
    tool_registry = init_tool_registry(adb_bridge)

    # -----------------------------------------------------------------------
    # 3. Session Memory
    # -----------------------------------------------------------------------
    session_memory = init_session_memory()

    # -----------------------------------------------------------------------
    # 4. Print startup banner
    # -----------------------------------------------------------------------
    print_banner(adb_manager, tool_registry)

    # -----------------------------------------------------------------------
    # 5. Graceful shutdown handler
    # -----------------------------------------------------------------------
    memory_path = os.environ.get("ARIA_MEMORY_PATH", "memory/session.json")

    def handle_shutdown(signum, frame):
        logger.info("Shutdown signal received — saving session memory…")
        try:
            session_memory.save(memory_path)
            logger.info("Session memory saved to %s", memory_path)
        except Exception as exc:
            logger.warning("Could not save session memory: %s", exc)

        if adb_manager is not None:
            adb_manager.stop_auto_reconnect()

        logger.info("Aria OS agent stopped.")
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    # -----------------------------------------------------------------------
    # 6. Start FastAPI server (blocks)
    # -----------------------------------------------------------------------
    from agent.server import start_server

    host = os.environ.get("ARIA_HOST", "0.0.0.0")
    port = int(os.environ.get("ARIA_PORT", "8765"))
    logger.info("Starting Aria server at http://%s:%d", host, port)
    start_server(host=host, port=port)


if __name__ == "__main__":
    main()
