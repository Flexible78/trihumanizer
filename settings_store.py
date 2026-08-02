"""Persistent local settings for the AI provider, model and API keys.

Two requirements hold at the same time:

1. the browser must never receive a raw API key, and
2. a local install must not ask for provider, model and key again after every
   application restart.

Both are satisfied by keeping the last used provider/model plus per-provider
credentials on the server side in data/settings.json, written atomically and
restricted to the current user. Only boolean "a key is stored" flags are ever
exposed to the frontend.

Hosted deployments (Vercel) have a read-only filesystem, so persistence is
disabled there and credentials come from environment variables only.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent
SETTINGS_PATH = BASE_DIR / "data" / "settings.json"

MAX_KEY_LENGTH = 512
MAX_MODEL_LENGTH = 200
MAX_URL_LENGTH = 500
MAX_ID_LENGTH = 60

_CACHE: dict[str, Any] | None = None


def hosted_mode() -> bool:
    """True when the filesystem is read-only and settings cannot be stored."""
    return bool(os.environ.get("VERCEL") or os.environ.get("TRIHUMANIZER_HOSTED"))


def _blank() -> dict[str, Any]:
    return {"provider": "", "model": "", "custom_url": "", "providers": {}}


def _sanitize(raw: Any) -> dict[str, Any]:
    """Normalize untrusted file content into the documented structure."""
    data = _blank()
    if not isinstance(raw, dict):
        return data
    data["provider"] = str(raw.get("provider") or "").strip().lower()[:MAX_ID_LENGTH]
    data["model"] = str(raw.get("model") or "").strip()[:MAX_MODEL_LENGTH]
    data["custom_url"] = str(raw.get("custom_url") or "").strip()[:MAX_URL_LENGTH]
    providers = raw.get("providers")
    if isinstance(providers, dict):
        for provider, entry in providers.items():
            if not isinstance(entry, dict):
                continue
            provider_id = str(provider).strip().lower()[:MAX_ID_LENGTH]
            if not provider_id:
                continue
            data["providers"][provider_id] = {
                "api_key": str(entry.get("api_key") or "").strip()[:MAX_KEY_LENGTH],
                "model": str(entry.get("model") or "").strip()[:MAX_MODEL_LENGTH],
                "custom_url": str(entry.get("custom_url") or "").strip()[:MAX_URL_LENGTH],
            }
    return data


def read_settings(refresh: bool = False) -> dict[str, Any]:
    """Return the stored settings, loading them from disk once per process."""
    global _CACHE
    if _CACHE is not None and not refresh:
        return _CACHE
    if hosted_mode():
        _CACHE = _blank()
        return _CACHE
    try:
        raw = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raw = {}
    _CACHE = _sanitize(raw)
    return _CACHE


def _write(data: dict[str, Any]) -> bool:
    """Persist settings atomically. Returns False when storage is unavailable."""
    global _CACHE
    _CACHE = data
    if hosted_mode():
        return False
    try:
        SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        temp_path = SETTINGS_PATH.with_name(SETTINGS_PATH.name + ".tmp")
        temp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temp_path, SETTINGS_PATH)
        try:
            os.chmod(SETTINGS_PATH, 0o600)
        except OSError:
            pass
        return True
    except OSError:
        return False


def provider_entry(provider: str) -> dict[str, str]:
    provider = str(provider or "").strip().lower()
    entry = read_settings()["providers"].get(provider) or {}
    return {
        "api_key": str(entry.get("api_key") or ""),
        "model": str(entry.get("model") or ""),
        "custom_url": str(entry.get("custom_url") or ""),
    }


def stored_api_key(provider: str) -> str:
    """The API key the user saved for this provider, or an empty string."""
    return provider_entry(provider)["api_key"]


def remember_settings(
    *,
    provider: str,
    model: str = "",
    custom_url: str = "",
    api_key: str = "",
    clear_key: bool = False,
) -> bool:
    """Save the active selection. Empty values keep the previous value.

    api_key is stored only when a non-empty value is supplied, so the UI can
    keep sending an empty override field while a key is already stored.
    clear_key=True removes the stored key for the provider.
    """
    provider = str(provider or "").strip().lower()[:MAX_ID_LENGTH]
    if not provider:
        return False

    data = _sanitize(read_settings())
    entry = data["providers"].get(provider) or {"api_key": "", "model": "", "custom_url": ""}

    model = str(model or "").strip()[:MAX_MODEL_LENGTH]
    custom_url = str(custom_url or "").strip()[:MAX_URL_LENGTH]
    api_key = str(api_key or "").strip()[:MAX_KEY_LENGTH]

    if model:
        entry["model"] = model
    if custom_url:
        entry["custom_url"] = custom_url
    if clear_key:
        entry["api_key"] = ""
    elif api_key:
        entry["api_key"] = api_key

    data["providers"][provider] = entry
    data["provider"] = provider
    if entry["model"]:
        data["model"] = entry["model"]
    data["custom_url"] = entry["custom_url"]
    return _write(data)


def forget_provider(provider: str) -> bool:
    """Remove everything stored for one provider (used by the UI reset)."""
    provider = str(provider or "").strip().lower()
    data = _sanitize(read_settings())
    if provider in data["providers"]:
        data["providers"].pop(provider, None)
        return _write(data)
    return False


def public_state() -> dict[str, Any]:
    """Secret-free view of the stored settings, safe to send to the browser."""
    data = read_settings()
    return {
        "provider": data["provider"],
        "model": data["model"],
        "customUrl": data["custom_url"],
        "persisted": not hosted_mode(),
        "providers": {
            provider: {
                "model": entry.get("model", ""),
                "customUrl": entry.get("custom_url", ""),
                "hasKey": bool(entry.get("api_key")),
            }
            for provider, entry in data["providers"].items()
        },
    }
