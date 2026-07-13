"""Upload all changed files to HF Spaces using huggingface_hub API."""
import os
import sys
from huggingface_hub import upload_file, upload_folder

REPO_ID = "Nawaz-khan-Droid/personal-voice-assistant"
token = os.environ.get("HF_TOKEN", "").strip() or (sys.argv[1].strip() if len(sys.argv) > 1 else "")
if not token:
    print("Usage: python upload_to_hf.py <HF_TOKEN>")
    print("   or: HF_TOKEN=xxx python upload_to_hf.py")
    sys.exit(1)

base = os.path.dirname(os.path.abspath(__file__))

# Backend files to upload (all .py files under backend/)
backend_files = [
    "backend/__init__.py",
    "backend/main.py",
    "backend/config.py",
    "backend/websocket_manager.py",
    # Security
    "backend/security/__init__.py",
    # Utils
    "backend/utils/__init__.py",
    "backend/utils/logger.py",
    "backend/utils/exceptions.py",
    "backend/utils/retry.py",
    "backend/utils/timeout.py",
    # Services
    "backend/services/__init__.py",
    "backend/services/duckduckgo_service.py",
    "backend/services/command_logger.py",
    # Services - AI
    "backend/services/ai/__init__.py",
    "backend/services/ai/tts_service.py",
    "backend/services/ai/stt_service.py",
    "backend/services/ai/llm_service.py",
    "backend/services/ai/voice_service.py",
    # Services - Tools
    "backend/services/tools/__init__.py",
    "backend/services/tools/tool_executor.py",
    "backend/services/tools/tool_registry.py",
    "backend/services/tools/builtin/calculator_tool.py",
    "backend/services/tools/builtin/search_tool.py",
    "backend/services/tools/builtin/time_tool.py",
    "backend/services/tools/builtin/weather_tool.py",
    # Services - cache
    "backend/services/cache/__init__.py",
    "backend/services/cache/response_cache.py",
]

# Frontend source files to upload (Vanilla JS)
frontend_files = [
    "backend/static/index.html",
    "README.md",
]

# Dockerfile
root_files = [
    "Dockerfile",
    "requirements.txt",
]

all_files = backend_files + frontend_files + root_files

for rel_path in all_files:
    full_path = os.path.join(base, rel_path)
    if not os.path.exists(full_path):
        print(f"SKIP (not found): {rel_path}")
        continue
    try:
        upload_file(
            path_or_fileobj=full_path,
            path_in_repo=rel_path,
            repo_id=REPO_ID,
            repo_type="space",
            token=token,
        )
        print(f"OK: {rel_path}")
    except Exception as e:
        print(f"FAIL: {rel_path} -> {e}")

# Force a Space rebuild by creating a timestamp file
try:
    from huggingface_hub import upload_file as _uf
    import time
    import tempfile
    ts = tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w")
    ts.write(f"rebuild trigger {time.time()}\n")
    ts.close()
    _uf(
        path_or_fileobj=ts.name,
        path_in_repo=".trigger_rebuild",
        repo_id=REPO_ID,
        repo_type="space",
        token=token,
    )
    os.unlink(ts.name)
    print("\nSpace rebuild triggered!")
except Exception as e:
    print(f"\nCould not force rebuild ({e}). Build should trigger automatically.")

print("\nDone! Check your Space logs at https://huggingface.co/spaces/Nawaz-khan-Droid/personal-voice-assistant")
