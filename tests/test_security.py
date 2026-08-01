"""Security tests: secrets never reach HTML/JS/API, password gate works."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


SECRET_MARKERS = [
    "sk-", "gsk_", "AIza", "ghp_", "gho_", "xoxb-",
]


def test_no_keys_in_html() -> None:
    html = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
    for marker in SECRET_MARKERS:
        assert marker not in html, f"secret marker {marker} found in HTML"
    assert "api_key" not in html.casefold().replace("api key override", ""), "api_key field leak"


def test_no_keys_in_js() -> None:
    for name in ("app.js", "speech.js", "layout-corrector.js", "sw.js"):
        text = (ROOT / "static" / name).read_text(encoding="utf-8")
        for marker in SECRET_MARKERS:
            assert marker not in text, f"{name} contains {marker}"


def test_no_keys_in_api_config() -> None:
    from app import app

    client = app.test_client()
    response = client.get("/api/config")
    assert response.status_code == 200
    serialized = json.dumps(response.get_json(), ensure_ascii=False)
    for marker in SECRET_MARKERS:
        assert marker not in serialized, f"secret marker {marker} in /api/config"
    payload = response.get_json()
    for provider, spec in payload.get("providers", {}).items():
        assert "key" not in {k.lower() for k in spec.keys()}, spec
        assert isinstance(spec.get("configuredKey"), bool)


def test_no_keys_in_tracked_files() -> None:
    if not (ROOT / ".git").exists():
        return  # not a git repo yet — covered by CI after push
    result = subprocess.run(
        ["git", "grep", "-I", "-n", "-E", "sk-[A-Za-z0-9]{20,}|gsk_[A-Za-z0-9]{20,}|AIza[0-9A-Za-z_-]{20,}"],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        timeout=30,
    )
    assert result.returncode != 0, f"secrets found in git-tracked files:\n{result.stdout}"


def test_password_gate_works_when_enabled() -> None:
    os.environ["APP_PASSWORD"] = "test-pass-123"
    os.environ["FLASK_SECRET_KEY"] = "unit-test-secret"
    try:
        # Re-import with the password set.
        import importlib

        import app as app_module

        importlib.reload(app_module)
        client = app_module.app.test_client()

        # Public shell remains visible.
        assert client.get("/").status_code == 200
        assert client.get("/api/health").status_code == 200

        # AI endpoints require auth.
        resp = client.post("/api/process", json={"text": "hello"})
        assert resp.status_code == 401, resp.status_code

        # Wrong password fails.
        resp = client.post("/api/auth/login", json={"password": "wrong"})
        assert resp.status_code == 401

        # Correct password unlocks.
        resp = client.post("/api/auth/login", json={"password": "test-pass-123"})
        assert resp.status_code == 200
        assert resp.get_json()["ok"] is True

        # Protected endpoint now works (400 expected: missing model/text).
        resp = client.post("/api/process", json={"text": "hello", "provider": "mistral"})
        assert resp.status_code in {200, 400, 502}, resp.status_code

        # Logout re-locks.
        client.post("/api/auth/logout")
        resp = client.post("/api/process", json={"text": "hello"})
        assert resp.status_code == 401
    finally:
        os.environ.pop("APP_PASSWORD", None)
        os.environ.pop("FLASK_SECRET_KEY", None)


def test_password_gate_optional() -> None:
    os.environ.pop("APP_PASSWORD", None)
    os.environ.pop("FLASK_SECRET_KEY", None)
    import importlib

    import app as app_module

    importlib.reload(app_module)
    client = app_module.app.test_client()
    resp = client.post("/api/process", json={"text": "hello", "provider": "mistral"})
    # No auth required -> validation errors or provider error, never 401.
    assert resp.status_code != 401, resp.status_code


if __name__ == "__main__":
    test_no_keys_in_html()
    test_no_keys_in_js()
    test_no_keys_in_api_config()
    test_no_keys_in_tracked_files()
    test_password_gate_works_when_enabled()
    test_password_gate_optional()
    print("SECURITY TESTS OK")
