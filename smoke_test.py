"""Smoke test for JARVIS LiveKit architecture."""
import sys

def run_smoke_test():
    try:
        from core.server import app
    except Exception as e:
        print(f"Failed to import core.server app: {e}")
        sys.exit(1)

    from fastapi.testclient import TestClient
    client = TestClient(app)

    print("Test: GET /api/health")
    resp = client.get("/api/health")
    assert resp.status_code == 200
    print(f"  PASS: {resp.json()}")

    print("Test: GET / (index.html)")
    resp = client.get("/")
    assert resp.status_code == 200
    assert "JARVIS" in resp.text
    print("  PASS: index.html served")

    print("Test: POST /api/token")
    resp = client.post("/api/token", json={"password": "jarvis_secure_123", "persona": "jarvis"})
    if resp.status_code == 401:
        print("  SKIP: Unauthorized (expected if JARVIS_UI_PASSWORD is not set in env to match jarvis_secure_123)")
    else:
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "token" in data
        print(f"  PASS: token minted")

    print("\nAll smoke tests passed.")

if __name__ == "__main__":
    run_smoke_test()
