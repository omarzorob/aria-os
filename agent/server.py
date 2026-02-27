"""
P2-1: Aria Agent HTTP/WebSocket Server

FastAPI server that the Flutter UI communicates with on port 8765.
Exposes REST endpoints and a WebSocket for streaming responses.

Environment variables:
    ANTHROPIC_API_KEY: Anthropic API key
    OPENAI_API_KEY: OpenAI API key
    ARIA_HOST: Server host (default: 0.0.0.0)
    ARIA_PORT: Server port (default: 8765)
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import uvicorn
from fastapi import FastAPI, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agent.aria_agent import AriaAgent

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class ChatRequest(BaseModel):
    """Chat request payload from Flutter UI."""

    message: str
    session_id: str | None = None


class ChatResponse(BaseModel):
    """Chat response payload."""

    response: str
    session_id: str | None = None
    tokens_used: int | None = None
    duration_ms: float | None = None


class TranscriptResponse(BaseModel):
    """Voice transcription response."""

    transcript: str
    confidence: float | None = None


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    version: str


class StatusResponse(BaseModel):
    """Agent status response."""

    status: str
    active_tools: list[str]
    memory_stats: dict
    uptime_seconds: float
    requests_served: int


# ---------------------------------------------------------------------------
# App state
# ---------------------------------------------------------------------------

_agent: AriaAgent | None = None
_start_time: float = time.time()
_requests_served: int = 0


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """Initialize and teardown the agent on startup/shutdown."""
    global _agent, _start_time

    logger.info("Starting Aria agent server…")
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    _agent = AriaAgent(api_key=api_key)
    _start_time = time.time()
    logger.info("Aria agent ready.")

    yield

    logger.info("Shutting down Aria agent server.")


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Aria OS Agent API",
    description="AI-native Android assistant backend for the Flutter UI",
    version="1.0.0",
    lifespan=lifespan,
)

# Allow Flutter dev server + any local origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/health", response_model=HealthResponse, tags=["system"])
async def health() -> HealthResponse:
    """Health check — returns OK when the server is running."""
    return HealthResponse(status="ok", version="1.0.0")


@app.get("/status", response_model=StatusResponse, tags=["system"])
async def status() -> StatusResponse:
    """Return agent status, active tools, and memory statistics."""
    global _agent, _start_time, _requests_served

    active_tools: list[str] = []
    memory_stats: dict = {}

    if _agent is not None:
        # Collect tool names if agent has a tool registry
        if hasattr(_agent, "tool_registry") and _agent.tool_registry:
            try:
                from agent.tool_registry import all_tools
                active_tools = [t.name for t in all_tools()]
            except Exception:
                active_tools = []

        # Collect memory stats if agent has memory
        if hasattr(_agent, "history"):
            memory_stats = {
                "history_turns": len(_agent.history),
            }

    return StatusResponse(
        status="running" if _agent else "initializing",
        active_tools=active_tools,
        memory_stats=memory_stats,
        uptime_seconds=round(time.time() - _start_time, 2),
        requests_served=_requests_served,
    )


@app.post("/chat", response_model=ChatResponse, tags=["chat"])
async def chat(req: ChatRequest) -> ChatResponse:
    """
    Process a chat message and return Aria's response.

    The agent runs synchronously in a thread pool to avoid blocking the
    event loop during LLM calls.
    """
    global _agent, _requests_served

    if _agent is None:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    start = time.time()
    _requests_served += 1

    try:
        # Run the blocking agent call in a thread pool
        loop = asyncio.get_event_loop()
        response_text = await loop.run_in_executor(None, _agent.run, req.message)
    except Exception as exc:
        logger.exception("Agent error during chat: %s", exc)
        raise HTTPException(status_code=500, detail=f"Agent error: {exc}") from exc

    duration_ms = (time.time() - start) * 1000
    return ChatResponse(
        response=response_text,
        session_id=req.session_id,
        duration_ms=round(duration_ms, 2),
    )


@app.post("/voice/transcribe", response_model=TranscriptResponse, tags=["voice"])
async def transcribe_voice(file: UploadFile) -> TranscriptResponse:
    """
    Transcribe uploaded audio bytes to text.

    Accepts audio in any format supported by whisper (wav, mp3, m4a, etc.).
    Falls back to a stub response if whisper is not available.
    """
    audio_bytes = await file.read()

    try:
        import io
        import tempfile

        import whisper  # type: ignore

        # Save to temp file and transcribe
        suffix = ".wav"
        if file.filename:
            suffix = "." + file.filename.split(".")[-1]

        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        model = whisper.load_model("base")
        result = model.transcribe(tmp_path)
        transcript = result.get("text", "").strip()

        import os as _os
        _os.unlink(tmp_path)

        return TranscriptResponse(transcript=transcript)

    except ImportError:
        logger.warning("whisper not available — returning stub transcript")
        return TranscriptResponse(
            transcript="[whisper not installed — install openai-whisper for transcription]",
            confidence=0.0,
        )
    except Exception as exc:
        logger.exception("Transcription failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Transcription error: {exc}") from exc


@app.websocket("/stream")
async def stream_websocket(websocket: WebSocket) -> None:
    """
    WebSocket endpoint for streaming Aria responses.

    Client sends: {"message": "..."}
    Server streams: text chunks, then {"done": true}
    """
    global _agent, _requests_served

    await websocket.accept()
    logger.info("WebSocket connection opened")

    try:
        while True:
            data = await websocket.receive_json()
            message = data.get("message", "")
            if not message:
                await websocket.send_json({"error": "Empty message"})
                continue

            _requests_served += 1

            if _agent is None:
                await websocket.send_json({"error": "Agent not initialized"})
                continue

            try:
                # Stream response word by word for a smooth UX
                loop = asyncio.get_event_loop()
                response_text = await loop.run_in_executor(None, _agent.run, message)

                # Simulate token streaming by yielding chunks
                words = response_text.split()
                for i, word in enumerate(words):
                    chunk = word + (" " if i < len(words) - 1 else "")
                    await websocket.send_json({"chunk": chunk})
                    await asyncio.sleep(0.02)  # ~50 words/second

                await websocket.send_json({"done": True, "full_response": response_text})

            except Exception as exc:
                logger.exception("Agent error in WebSocket: %s", exc)
                await websocket.send_json({"error": str(exc)})

    except WebSocketDisconnect:
        logger.info("WebSocket connection closed")
    except Exception as exc:
        logger.exception("Unexpected WebSocket error: %s", exc)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def start_server(
    host: str | None = None,
    port: int | None = None,
    reload: bool = False,
) -> None:
    """Start the Aria agent server with uvicorn."""
    _host = host or os.environ.get("ARIA_HOST", "0.0.0.0")
    _port = port or int(os.environ.get("ARIA_PORT", "8765"))

    logger.info("Starting Aria server on %s:%d", _host, _port)
    uvicorn.run(
        "agent.server:app",
        host=_host,
        port=_port,
        reload=reload,
        log_level="info",
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    start_server()
