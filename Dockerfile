# ── Hugging Face Spaces Dockerfile for JARVIS Voice Assistant ──

# ── STAGE 1: Frontend Build ──
FROM python:3.10-slim AS builder

WORKDIR /app

# python:3.10-slim ships nodejs v12 which is too old for Vite (requires Node 16+).
# NodeSource gives us Node 20.
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install frontend deps and build
COPY frontend/package.json frontend/package-lock.json frontend/
RUN cd frontend && npm ci
COPY frontend/ frontend/
RUN cd frontend && npm run build

# ── STAGE 2: Runtime ──
FROM python:3.10-slim

# tini: tiny init process that handles SIGTERM forwarding and zombie reaping.
# Without tini, HF's stop/redeploy commands hang because background processes
# don't receive SIGTERM.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    tini \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade -r requirements.txt

# Application code — only what the runtime needs
COPY core/ /app/core/
COPY profiles/ /app/profiles/
COPY services/ /app/services/
COPY --from=builder /app/frontend/dist/ /app/frontend/dist/

# Directory for SQLite memory DB at runtime
RUN mkdir -p /app/core/static

WORKDIR /app

# HF Spaces injects SPACE_PORT — default to 7860.
# This MUST match app_port in README.md frontmatter.
ENV PORT=7860
EXPOSE 7860

# Set thread limits for both processes.
# These MUST be set here (not just in worker.py) because uvicorn
# runs in a separate process and won't pick up Python-level os.environ calls.
ENV OMP_NUM_THREADS=2
ENV OPENBLAS_NUM_THREADS=2
ENV MKL_NUM_THREADS=2

# CMD structure:
#   tini --     → PID 1, handles signals cleanly
#   sh -c "..."  → runs both processes
#   uvicorn ... & → FastAPI (React UI + /api/token) in background
#   python -m core.worker → LiveKit agent in foreground (keeps container alive)
#
# Worker is foreground: if it exits, the container exits. This is the correct
# liveness model — the worker is the primary service.
CMD ["tini", "--", "sh", "-c", "uvicorn core.server:app --host 0.0.0.0 --port ${PORT:-7860} & python -m core.worker"]
