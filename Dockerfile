# ============================================================
# STAGE 1: Build Next.js frontend (static export)
# ============================================================
FROM node:20-alpine AS frontend-builder

WORKDIR /build
COPY client/package.json client/package-lock.json* ./
RUN npm ci

COPY client/ .
RUN npm run build

# ============================================================
# STAGE 2: Python backend + frontend assets
# ============================================================
FROM python:3.10-slim

WORKDIR /code

# System deps — only what's needed at runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY backend/ backend/

# Copy pre-built frontend from stage 1
COPY --from=frontend-builder /build/out/ client/out/

# Kokoro model download (configurable via build args)
ARG KOKORO_MODEL_URL=https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0
RUN python -c "
import os, urllib.request
base = os.environ.get('KOKORO_MODEL_URL', '$KOKORO_MODEL_URL')
for f in ['kokoro-v1.0.onnx', 'voices-v1.0.bin']:
    path = f'backend/static/{f}'
    if not os.path.exists(path):
        print(f'Downloading {f}...')
        urllib.request.urlretrieve(f'{base}/{f}', path)
"

# Hugging Face Spaces
EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:7860/health')"

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "7860", "--ws", "wsproto"]
