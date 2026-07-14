"""Deploy to HF Spaces via API commit + restart."""
import os, sys
from huggingface_hub import HfApi, CommitOperationAdd

import getpass
token = os.environ.get("HF_TOKEN", "").strip() or (sys.argv[1].strip() if len(sys.argv) > 1 else "")
if not token:
    token = getpass.getpass("HF Token (hidden): ")

REPO_ID = "Nawaz-khan-Droid/personal-voice-assistant"
api = HfApi(token=token)
base = os.path.dirname(os.path.abspath(__file__))

operations = []

# Backend Python files
for root, dirs, files in os.walk(os.path.join(base, "backend")):
    for f in files:
        if f.endswith(".py"):
            path = os.path.join(root, f)
            rel = os.path.relpath(path, base)
            operations.append(CommitOperationAdd(path_in_repo=rel, path_or_fileobj=path))

# Root files
for f in ["Dockerfile", "requirements.txt", "dev_server.py", "startup.sh"]:
    path = os.path.join(base, f)
    if os.path.exists(path):
        operations.append(CommitOperationAdd(path_in_repo=f, path_or_fileobj=path))

print(f"Committing {len(operations)} files...")
api.create_commit(
    repo_id=REPO_ID,
    repo_type="space",
    revision="master",
    operations=operations,
    commit_message="deploy: LiveKit architecture, quantized models, chat+transcript support",
)
print("Commit created on HF Spaces.")

api.restart_space(REPO_ID)
print("Space restart triggered. Check logs in 2 min.")
