"""Provider catalog and server-side credential resolution.

Keys are read only from server-side environment variables (or an optional
local ``.env`` file) and are never serialized into the browser.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from settings_store import public_state as stored_public_state
from settings_store import stored_api_key

BASE_DIR = Path(__file__).resolve().parent

try:  # Optional local development convenience; never required in production.
    from dotenv import load_dotenv

    load_dotenv(BASE_DIR / ".env")
except Exception:  # pragma: no cover - dotenv is optional
    pass

APP_VERSION = "1.6.3"
DEFAULT_PROVIDER = "mistral"
DEFAULT_MODEL = "mistral-large-latest"

# Provider id -> environment variable that holds the API key.
ENV_KEY_MAP: dict[str, str] = {
    "mistral": "MISTRAL_API_KEY",
    "groq": "GROQ_API_KEY",
    "google_studio": "GOOGLE_STUDIO_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "omniroute": "OMNIROUTE_API_KEY",
    "freeway": "FREEWAY_API_KEY",
    "openai": "OPENAI_API_KEY",
    "ollama": "",
    "custom": "",
}

# Public catalog. All user-visible copy is English.
PROVIDER_CATALOG: dict[str, dict[str, Any]] = {
    "mistral": {
        "label": "Mistral · primary",
        "short_label": "Mistral",
        "base_url": "https://api.mistral.ai/v1",
        "last_model_key": "Mistral",
        "default_model": DEFAULT_MODEL,
        "requires_key": True,
        "accent": "coral",
        "help": "Primary cloud provider. Mistral Large is the default model; leave the key field empty when the key is configured on the server.",
    },
    "groq": {
        "label": "Groq · fast",
        "short_label": "Groq",
        "base_url": "https://api.groq.com/openai/v1",
        "last_model_key": "Groq (OSS 120b)",
        "default_model": "openai/gpt-oss-120b",
        "requires_key": True,
        "accent": "orange",
        "help": "Fast OpenAI-compatible Groq endpoint. Good for short messages and quick drafts.",
    },
    "google_studio": {
        "label": "Google AI Studio",
        "short_label": "Google Studio",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "last_model_key": "Google Studio (Gemma 4)",
        "default_model": "models/gemma-4-31b-it",
        "requires_key": True,
        "accent": "blue",
        "help": "Google AI Studio via its OpenAI-compatible endpoint.",
    },
    "openrouter": {
        "label": "OpenRouter",
        "short_label": "OpenRouter",
        "base_url": "https://openrouter.ai/api/v1",
        "default_model": "openrouter/free",
        "requires_key": True,
        "accent": "violet",
        "help": "Catalog of many models. Use Refresh models to load the current list.",
    },
    "omniroute": {
        "label": "OmniRoute · local gateway",
        "short_label": "OmniRoute",
        "base_url": "http://localhost:20128",
        "last_model_key": "OmniRoute",
        "default_model": "kilocode/openrouter/free",
        "requires_key": True,
        "accent": "teal",
        "help": "Local OmniRoute gateway on localhost:20128. Must be started separately.",
    },
    "freeway": {
        "label": "Freeway · local gateway",
        "short_label": "Freeway",
        "base_url": "http://127.0.0.1:8787/v1",
        "last_model_key": "Freeway",
        "default_model": "nemotron-3-ultra-550b-a55b",
        "default_key": "123",
        "requires_key": True,
        "accent": "green",
        "help": "Local Freeway gateway on 127.0.0.1:8787/v1.",
    },
    "openai": {
        "label": "OpenAI",
        "short_label": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4.1-mini",
        "requires_key": True,
        "accent": "slate",
        "help": "Direct OpenAI endpoint. Set OPENAI_API_KEY on the server.",
    },
    "ollama": {
        "label": "Ollama · offline",
        "short_label": "Ollama",
        "base_url": "http://127.0.0.1:11434/v1",
        "default_model": "qwen3:8b",
        "requires_key": False,
        "accent": "gray",
        "help": "Local Ollama. No API key is required, but Ollama and the selected model must be installed and running.",
    },
    "custom": {
        "label": "Other OpenAI-compatible API",
        "short_label": "Custom API",
        "base_url": "",
        "default_model": "",
        "requires_key": False,
        "accent": "gray",
        "help": "Enter your own base endpoint. The key field may stay empty for local services without authentication.",
    },
}

_ALLOWED_MODEL_PATTERN = (  # allowlist pattern for model strings
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._:/+- "
)


def provider_spec(provider: str) -> dict[str, Any]:
    return PROVIDER_CATALOG.get(provider.strip().lower(), {})


def is_allowed_provider(provider: str) -> bool:
    return provider.strip().lower() in PROVIDER_CATALOG


def is_allowed_model(model: str) -> bool:
    model = (model or "").strip()
    if not model or len(model) > 200:
        return False
    return all(ch in _ALLOWED_MODEL_PATTERN for ch in model)


def provider_default_model(provider: str) -> str:
    provider = provider.strip().lower()
    spec = provider_spec(provider)
    return str(spec.get("default_model") or "")


def environment_api_key(provider: str) -> str:
    """Read the API key for a provider from environment variables only."""
    provider = provider.strip().lower()
    env_name = ENV_KEY_MAP.get(provider, "")
    if env_name:
        value = os.environ.get(env_name, "").strip()
        if value:
            return value
    # Legacy generic prefix still respected for backward compatibility.
    legacy = os.environ.get(f"TRIHUMANIZER_{provider.upper().replace('-', '_')}_API_KEY", "").strip()
    if legacy:
        return legacy
    # Legacy single-key fallback for the original Mistral-based app.
    if provider == "mistral":
        return os.environ.get("TRIHUMANIZER_API_KEY", "").strip()
    return ""


def resolve_api_key(provider: str, override: str = "") -> str:
    """Resolve the effective key for a provider.

    Order of precedence:
    1. the override sent with the request (key typed in the UI right now),
    2. the key the user saved locally (survives application restarts),
    3. server-side environment variables or .env,
    4. the built-in default key of the provider (local gateways only).
    """
    override = str(override or "").strip()
    if override:
        return override
    saved = stored_api_key(provider)
    if saved:
        return saved
    from_env = environment_api_key(provider)
    if from_env:
        return from_env
    return str(provider_spec(provider).get("default_key") or "").strip()


# Ordered by output quality. Used for automatic failover when the selected
# model errors out, is rate limited or returns an unusable answer.
FALLBACK_MODEL_CHAIN: list[tuple[str, str]] = [
    ("mistral", "mistral-large-latest"),
    ("openai", "gpt-4.1-mini"),
    ("groq", "openai/gpt-oss-120b"),
    ("google_studio", "models/gemma-4-31b-it"),
    ("openrouter", "openrouter/free"),
    ("omniroute", "kilocode/openrouter/free"),
    ("freeway", "nemotron-3-ultra-550b-a55b"),
    ("ollama", "qwen3:8b"),
]

LOCAL_PROVIDERS = {"omniroute", "freeway", "ollama"}


# Same-provider ladders keep failover working when only one API key exists.
PROVIDER_MODEL_LADDER: dict[str, list[str]] = {
    "mistral": [
        "mistral-large-latest",
        "mistral-medium-latest",
        "mistral-small-latest",
        "open-mistral-nemo",
    ],
    "groq": ["openai/gpt-oss-120b", "llama-3.3-70b-versatile", "openai/gpt-oss-20b"],
    "openai": ["gpt-4.1-mini", "gpt-4o-mini"],
    "google_studio": ["models/gemma-4-31b-it"],
    "openrouter": ["openrouter/free"],
}


def fallback_candidates(
    provider: str = "", model: str = "", allow_local: bool = True, api_key: str = ""
) -> list[dict[str, str]]:
    """Next best provider/model pairs that can actually be called right now.

    The same provider is tried first with its next best model, so failover also
    works when only one API key is configured.
    """
    provider = (provider or "").strip().lower()
    model = (model or "").strip()
    candidates: list[dict[str, str]] = []
    seen = {(provider, model)}
    same_key = (api_key or "").strip() or resolve_api_key(provider)
    same_spec = provider_spec(provider)
    if same_spec and (same_key or not same_spec.get("requires_key")):
        for ladder_model in PROVIDER_MODEL_LADDER.get(provider, []):
            if (provider, ladder_model) in seen:
                continue
            seen.add((provider, ladder_model))
            candidates.append(
                {"provider": provider, "model": ladder_model, "api_key": same_key}
            )
    for candidate_provider, candidate_model in FALLBACK_MODEL_CHAIN:
        if (candidate_provider, candidate_model) in seen:
            continue
        if candidate_provider == provider and candidate_model == model:
            continue
        if candidate_provider in LOCAL_PROVIDERS and not allow_local:
            continue
        spec = provider_spec(candidate_provider)
        if not spec:
            continue
        key = resolve_api_key(candidate_provider)
        if spec.get("requires_key") and not key:
            continue
        candidates.append(
            {"provider": candidate_provider, "model": candidate_model, "api_key": key}
        )
    return candidates


def public_config() -> dict[str, Any]:
    """Configuration safe to send to the browser. Never contains secrets."""
    providers: dict[str, dict[str, Any]] = {}
    for provider, spec in PROVIDER_CATALOG.items():
        effective_key = resolve_api_key(provider)
        providers[provider] = {
            "label": spec["label"],
            "shortLabel": spec["short_label"],
            "endpoint": spec.get("base_url", ""),
            "model": provider_default_model(provider),
            "requiresKey": bool(spec.get("requires_key")),
            "configuredKey": bool(effective_key),
            "savedKey": bool(stored_api_key(provider)),
            "envKey": bool(environment_api_key(provider)),
            "accent": spec.get("accent", "gray"),
            "help": spec.get("help", ""),
        }
    return {
        "version": APP_VERSION,
        "defaultProvider": DEFAULT_PROVIDER,
        "defaultModel": DEFAULT_MODEL,
        "saved": stored_public_state(),
        "providers": providers,
        "authRequired": bool(os.environ.get("APP_PASSWORD")),
        "researchEnabled": os.environ.get("RESEARCH_ENABLED", "").strip().lower() in {"1", "true", "yes", "on"},
        "hosted": bool(os.environ.get("VERCEL") or os.environ.get("TRIHUMANIZER_HOSTED")),
    }
