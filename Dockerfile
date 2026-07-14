FROM python:3.10-slim

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg libsndfile1 curl && rm -rf /var/lib/apt/lists/*

# LiveKit server (Linux amd64)
RUN curl -sSL https://get.livekit.io | bash

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade -r requirements.txt

# Application
COPY core/ /app/core/
COPY profiles/ /app/profiles/
COPY services/ /app/services/
COPY startup.sh /app/startup.sh
RUN chmod +x /app/startup.sh

# Download Kokoro quantized model (smaller, faster load)
RUN mkdir -p /app/core/static && python <<'EOF'
import os, urllib.request
base = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0"
for f in ["kokoro-v1.0.int8.onnx", "voices-v1.0.bin"]:
    path = f"/app/core/static/{f}"
    if not os.path.exists(path):
        print(f"Downloading {f}...")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        urllib.request.urlretrieve(f"{base}/{f}", path)
EOF

# Pre-cache Moonshine STT model (quantized if available, else float)
RUN python <<'EOF'
from huggingface_hub import hf_hub_download
import os
repo = "UsefulSensors/moonshine"
# Try quantized first, fall back to float
for subfolder in ["onnx/merged/tiny/int8", "onnx/merged/tiny/float"]:
    try:
        for f in ["encoder_model.onnx", "decoder_model_merged.onnx"]:
            path = hf_hub_download(repo, f, subfolder=subfolder)
            print(f"Cached {f}: {os.path.getsize(path)} bytes")
        print(f"Using {subfolder} Moonshine model")
        break
    except Exception:
        continue
EOF

WORKDIR /app
EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl -f http://localhost:7860/api/health || exit 1

CMD ["bash", "startup.sh"]
