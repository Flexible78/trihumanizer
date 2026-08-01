"""Live smoke test against a deployed TriHumanizer instance.

Verifies, in order:
1. /api/config — server-side key flags (no secrets are read or printed)
2. POST /api/auth/login — when APP_PASSWORD is enabled, authenticates with a
   password supplied via the TRIHUMANIZER_TEST_PASSWORD env var or --password
3. POST /api/test/key — provider authentication (endpoint reachable, key accepted)
4. POST /api/test/model — a real model generation call
5. POST /api/process — a full translation through the deployed app

Usage:
    python tools/live_smoke_test.py [BASE_URL] [PROVIDER] [MODEL] [--password ...]

Defaults: https://trihumanizer.vercel.app  mistral  mistral-large-latest

The password may also be provided via the TRIHUMANIZER_TEST_PASSWORD
environment variable. Never prints secrets: the app redacts errors, and this
script only reads the boolean configuredKey flag plus redacted responses.
"""
from __future__ import annotations

import argparse
import http.cookiejar
import json
import os
import urllib.error
import urllib.request

_parser = argparse.ArgumentParser(description="Live smoke test for a deployed TriHumanizer instance")
_parser.add_argument("base_url", nargs="?", default="https://trihumanizer.vercel.app", help="deployed base URL")
_parser.add_argument("provider", nargs="?", default="mistral", help="provider id (default: mistral)")
_parser.add_argument("model", nargs="?", default="mistral-large-latest", help="model name")
_parser.add_argument("--password", dest="password", default="", help="APP_PASSWORD for the auth gate (or set TRIHUMANIZER_TEST_PASSWORD)")
_args = _parser.parse_args()

if not _args.base_url.startswith(("http://", "https://")):
    _parser.error("base_url must start with http:// or https:// - positional order is [BASE_URL] [PROVIDER] [MODEL]")
BASE_URL = _args.base_url.rstrip("/")
PROVIDER = _args.provider
MODEL = _args.model
PASSWORD = _args.password or os.environ.get("TRIHUMANIZER_TEST_PASSWORD", "")

# Cookie jar keeps the session cookie across requests so login persists.
_opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))


def _read_json(resp):
    """Parse a response body as JSON; on failure return an empty dict."""
    try:
        return json.loads(resp.read().decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return {}


def _request(method: str, path: str, payload: dict | None = None):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"User-Agent": "trihumanizer-live-smoke"}
    if payload is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(BASE_URL + path, data=data, headers=headers, method=method)
    try:
        with _opener.open(req, timeout=90) as resp:
            return resp.status, _read_json(resp)
    except urllib.error.HTTPError as exc:
        # Surface the app's redacted error body instead of just the status line.
        body = _read_json(exc)
        message = str(body.get("error") or "") if isinstance(body, dict) else ""
        return exc.code, {"ok": False, "error": message or f"HTTP {exc.code}: {exc.reason}"}


def post(path: str, payload: dict):
    return _request("POST", path, payload)


def get(path: str):
    return _request("GET", path)


def main() -> int:
    failures: list[str] = []
    print(f"Live smoke test: {BASE_URL}  provider={PROVIDER}  model={MODEL}")

    # 1. Config: confirm the server-side key flag flipped on and read auth state.
    try:
        status, config = get("/api/config")
        print(f"[1] /api/config  -> {status}")
        spec = (config.get("providers") or {}).get(PROVIDER) or {}
        print(f"    {PROVIDER}: configuredKey={spec.get('configuredKey')} requiresKey={spec.get('requiresKey')}")
        if spec.get("requiresKey") and not spec.get("configuredKey"):
            failures.append("server-side key not configured (configuredKey=false)")
    except Exception as exc:  # noqa: BLE001
        failures.append(f"/api/config failed: {exc}")

    # 2. Auth gate: login when APP_PASSWORD is enabled.
    try:
        status, health = get("/api/health")
        auth_required = bool(health.get("auth_required"))
    except Exception as exc:  # noqa: BLE001
        failures.append(f"/api/health failed (cannot determine auth state): {exc}")
        print("\nFAILURES:")
        for item in failures:
            print(f"  - {item}")
        return 1
    if auth_required:
        if not PASSWORD:
            failures.append("APP_PASSWORD is enabled; set TRIHUMANIZER_TEST_PASSWORD or pass --password")
            print("\nFAILURES:")
            for item in failures:
                print(f"  - {item}")
            return 1
        try:
            status, data = post("/api/auth/login", {"password": PASSWORD})
            ok = status == 200 and data.get("ok")
            print(f"[2] /api/auth/login -> {status} ok={ok}")
            if not ok:
                failures.append(f"login failed: {data.get('error', '')[:200]}")
                print("\nFAILURES:")
                for item in failures:
                    print(f"  - {item}")
                return 1
        except Exception as exc:  # noqa: BLE001
            failures.append(f"/api/auth/login failed: {exc}")
            print("\nFAILURES:")
            for item in failures:
                print(f"  - {item}")
            return 1
    else:
        print("[2] /api/auth/login -> skipped (no password gate)")

    # 3. Key test: authentication only, no manual key (server env is used).
    try:
        status, data = post("/api/test/key", {"provider": PROVIDER})
        ok = status == 200 and data.get("ok")
        print(f"[3] /api/test/key -> {status} ok={ok} endpoint_reachable={data.get('endpoint_reachable')} "
              f"key_accepted={data.get('key_accepted')} elapsed_ms={data.get('elapsed_ms')}")
        if not ok:
            failures.append(f"key test failed: {data.get('error', '')[:200]}")
    except Exception as exc:  # noqa: BLE001
        failures.append(f"/api/test/key failed: {exc}")

    # 4. Model test: a real generation call.
    try:
        status, data = post("/api/test/model", {"provider": PROVIDER, "model": MODEL})
        ok = status == 200 and data.get("ok")
        reply = str(data.get("reply") or "").replace("\n", " ")[:120]
        print(f"[4] /api/test/model -> {status} ok={ok} elapsed_ms={data.get('elapsed_ms')}")
        print(f"    reply: {reply}")
        if not ok:
            failures.append(f"model test failed: {data.get('error', '')[:200]}")
    except Exception as exc:  # noqa: BLE001
        failures.append(f"/api/test/model failed: {exc}")

    # 5. Full translation through /api/process.
    try:
        status, data = post(
            "/api/process",
            {
                "text": "The quick brown fox jumps over the lazy dog.",
                "source_language": "auto",
                "target_language": "ru",
                "mode": "business",
                "action": "translate",
                "provider": PROVIDER,
                "model": MODEL,
            },
        )
        ok = status == 200 and data.get("ok")
        result = data.get("result") or {}
        translation = str(result.get("humanized_translation") or "").replace("\n", " ")[:160]
        print(f"[5] /api/process -> {status} ok={ok} action={data.get('action')} quality_retry={data.get('quality_retry')}")
        print(f"    translation: {translation}")
        if not ok:
            failures.append(f"process failed: {data.get('error', '')[:200]}")
    except Exception as exc:  # noqa: BLE001
        failures.append(f"/api/process failed: {exc}")

    if failures:
        print("\nFAILURES:")
        for item in failures:
            print(f"  - {item}")
        return 1
    print("\nLIVE SMOKE TEST OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
