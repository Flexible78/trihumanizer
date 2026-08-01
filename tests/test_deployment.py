"""Deployment tests: Flask/Vercel entrypoint, static assets, hosted mode."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def test_flask_app_imports() -> None:
    import app as app_module

    assert app_module.app is not None
    assert app_module.APP_VERSION == "1.6.0"
    assert callable(app_module.app.wsgi_app)


def test_local_app_starts() -> None:
    import app as app_module

    client = app_module.app.test_client()
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.get_json()["ok"] is True


def test_vercel_entrypoint() -> None:
    """The Vercel build uses app.py directly; ensure it exposes the WSGI app."""
    import app as app_module

    assert app_module.HOSTED in {True, False}
    # Vercel sets VERCEL=1; simulate it to prove hosted mode behavior.
    os.environ["VERCEL"] = "1"
    try:
        import importlib

        import app as reloaded

        importlib.reload(reloaded)
        assert reloaded.HOSTED is True
        client = reloaded.app.test_client()
        # Hosted history is empty (no SQLite writes).
        response = client.get("/api/history")
        assert response.status_code == 200
        assert response.get_json()["items"] == []
    finally:
        os.environ.pop("VERCEL", None)


def test_static_assets_load() -> None:
    import app as app_module

    client = app_module.app.test_client()
    for asset in [
        "/static/styles.css",
        "/static/app.js",
        "/static/speech.js",
        "/static/layout-corrector.js",
        "/static/icon-192.png",
        "/static/icon-512.png",
        "/manifest.webmanifest",
    ]:
        response = client.get(asset)
        assert response.status_code == 200, f"{asset} -> {response.status_code}"
        assert len(response.data) > 0


def test_api_route_works() -> None:
    import app as app_module

    client = app_module.app.test_client()
    response = client.get("/api/config")
    assert response.status_code == 200
    assert response.get_json()["defaultProvider"] == "mistral"


def test_hosted_no_sqlite_write() -> None:
    os.environ.pop("VERCEL", None)
    import importlib

    import app as app_module

    importlib.reload(app_module)
    assert app_module.HOSTED is False  # local context
    from storage import NullHistoryStore, hosted_mode, make_store

    os.environ["VERCEL"] = "1"
    try:
        assert hosted_mode() is True
        store = make_store(ROOT / "data" / "unused.db")
        assert isinstance(store, NullHistoryStore)
        store.add({"text": "secret"}, {"result": "x"})
        assert store.list() == []
    finally:
        os.environ.pop("VERCEL", None)


def test_vercel_config_valid() -> None:
    import json

    config = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))
    assert config["version"] == 2
    assert any(build["src"] == "app.py" for build in config["builds"])
    # Static assets must be served through the Flask lambda (@vercel/python
    # bundles them inside the function, so a filesystem dest 404s).
    routes = config["routes"]
    assert any(
        route.get("src") == "/static/(.*)" and route.get("dest") == "/app.py"
        for route in routes
    ), "static route must dest to /app.py"
    assert any(
        route.get("src") == "/(.*)" and route.get("dest") == "/app.py"
        for route in routes
    ), "catch-all route to /app.py missing"


def test_python_syntax_all() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "compileall", "-q", str(ROOT / "app.py"), str(ROOT / "llm_client.py"),
         str(ROOT / "provider_config.py"), str(ROOT / "intent.py"), str(ROOT / "research.py"),
         str(ROOT / "storage.py"), str(ROOT / "pdf_export.py"), str(ROOT / "quality.py"),
         str(ROOT / "prompts.py"), str(ROOT / "layout_check.py"), str(ROOT / "launcher.py")],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_js_syntax_all() -> None:
    for name in ("app.js", "speech.js", "layout-corrector.js", "sw.js"):
        result = subprocess.run(
            ["node", "--check", str(ROOT / "static" / name)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, f"{name}: {result.stdout}{result.stderr}"


if __name__ == "__main__":
    test_flask_app_imports()
    test_local_app_starts()
    test_vercel_entrypoint()
    test_static_assets_load()
    test_api_route_works()
    test_hosted_no_sqlite_write()
    test_vercel_config_valid()
    test_python_syntax_all()
    test_js_syntax_all()
    print("DEPLOYMENT TESTS OK")
