# ============================================================================
# Aria OS Agent Server — Docker Image
# ============================================================================
# Python 3.12-slim + Android SDK Platform Tools (adb) + agent dependencies
#
# NOTE: For Android device access in Docker, either:
#   a) Pass --device /dev/bus/usb to `docker run` for USB-connected devices
#   b) Use ADB over WiFi: set ANDROID_SERIAL=<ip>:5555 env var
#      and run `adb connect <ip>:5555` from inside the container.
# ============================================================================

FROM python:3.12-slim

# ---------------------------------------------------------------------------
# System dependencies
# ---------------------------------------------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
    android-tools-adb \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------
WORKDIR /app

# Copy dependency manifests first for better layer caching
COPY pyproject.toml ./
COPY uv.lock* ./

# Install pip and dependencies (using pip for Docker simplicity)
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
        fastapi>=0.110.0 \
        uvicorn[standard]>=0.29.0 \
        anthropic>=0.40.0 \
        openai>=1.30.0 \
        httpx>=0.27.0 \
        aiohttp>=3.9.0 \
        pydantic>=2.0.0

# Copy application source
COPY agent/ ./agent/
COPY main.py ./

# ---------------------------------------------------------------------------
# Runtime configuration
# ---------------------------------------------------------------------------
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    ARIA_HOST=0.0.0.0 \
    ARIA_PORT=8765

# Persistent memory volume mount point
VOLUME ["/app/memory"]

EXPOSE 8765

# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8765/health || exit 1

# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------
CMD ["python", "-m", "uvicorn", "agent.server:app", \
     "--host", "0.0.0.0", \
     "--port", "8765", \
     "--log-level", "info"]
