from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


PROVIDER_DEFAULTS = {
    "mistral": {"base_url": "https://api.mistral.ai/v1", "requires_key": True},
    "groq": {"base_url": "https://api.groq.com/openai/v1", "requires_key": True},
    "google_studio": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "requires_key": True,
    },
    "omniroute": {"base_url": "http://localhost:20128", "requires_key": True},
    "freeway": {
        "base_url": "http://127.0.0.1:8787/v1",
        "requires_key": True,
        "default_key": "123",
    },
    "openai": {"base_url": "https://api.openai.com/v1", "requires_key": True},
    "openrouter": {"base_url": "https://openrouter.ai/api/v1", "requires_key": True},
    "ollama": {"base_url": "http://127.0.0.1:11434/v1", "requires_key": False},
}



class LLMError(RuntimeError):
    pass


# Patterns that look like API keys or bearer tokens. Used to redact provider
# error messages before they are returned to the browser.
_SECRET_PATTERNS = [
    re.compile(r"(?i)\b(?:sk|gsk)[_-][a-z0-9_-]{16,}\b"),
    re.compile(r"(?i)\bAIza[0-9A-Za-z_\-]{20,}\b"),
    re.compile(r"(?i)\bgh[oprsu]_[0-9A-Za-z]{20,}\b"),
    re.compile(r"(?i)\bxox[baprs]-[0-9A-Za-z\-]{10,}\b"),
    re.compile(r"(?i)bearer\s+[a-z0-9._\-]{12,}"),
    re.compile(r"(?i)(api[_-]?key[\"' ]*[:=][\"' ]*)([^\s\"'\n,]{8,})"),
]


def redact_secrets(text: str) -> str:
    """Replace anything that looks like a credential with a placeholder."""
    if not text:
        return text
    redacted = str(text)
    for pattern in _SECRET_PATTERNS[:-1]:
        redacted = pattern.sub("[REDACTED]", redacted)
    key_label = _SECRET_PATTERNS[-1]
    redacted = key_label.sub(lambda match: f"{match.group(1)}[REDACTED]", redacted)
    return redacted


def _extract_content(data: dict[str, Any]) -> str:
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMError("Provider returned an unexpected response format.") from exc

    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") in {"text", "output_text"}:
                parts.append(str(item.get("text", "")))
        return "".join(parts)
    return str(content)


def _parse_json_object(content: str) -> dict[str, Any]:
    """Parse the model's JSON reply into a dict.

    Translation prompts return the five documented fields; write, research and
    intent prompts return additional structured fields (subject, body, sources,
    cleaned_request, ...). All keys are preserved so every flow works.
    """
    raw = content.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
    raw = re.sub(r"\s*```$", "", raw)

    candidates = [raw]
    first = raw.find("{")
    last = raw.rfind("}")
    if first >= 0 and last > first:
        candidates.append(raw[first:last + 1])

    for candidate in candidates:
        try:
            value = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if not isinstance(value, dict):
            continue
        result: dict[str, Any] = {
            "detected_language": str(value.get("detected_language", "")),
            "humanized_original": str(value.get("humanized_original", "")),
            "literal_translation": str(value.get("literal_translation", "")),
            "humanized_translation": str(value.get("humanized_translation", "")),
            "notes": str(value.get("notes", "")),
        }
        for key, item in value.items():
            if key not in result:
                result[key] = item
        return result

    raise LLMError(
        "The model did not return valid JSON. Try another model or run the request again."
    )


def _base_url(provider: str, custom_url: str) -> str:
    provider = provider.strip().lower()
    raw = (custom_url or PROVIDER_DEFAULTS.get(provider, {}).get("base_url", "")).strip()
    if not raw:
        raise LLMError("API endpoint is empty.")
    if not raw.startswith(("http://", "https://")):
        raise LLMError("API endpoint must start with http:// or https://.")
    return raw.rstrip("/")


def _endpoint_candidates(base: str, resource: str) -> list[str]:
    """Build tolerant OpenAI-compatible endpoint candidates.

    The user may provide either a base host (http://localhost:20128), a /v1 base,
    or a full endpoint. We keep the exact full endpoint when present and otherwise
    try the common OpenAI-compatible paths without duplicating /v1.
    """
    resource = resource.strip("/")
    parsed = urllib.parse.urlsplit(base)
    path = parsed.path.rstrip("/")

    if path.endswith(f"/{resource}") or path == f"/{resource}":
        return [base]

    candidates: list[str] = []
    if path.endswith("/v1"):
        candidates.append(f"{base}/{resource}")
    else:
        candidates.append(f"{base}/v1/{resource}")
        candidates.append(f"{base}/{resource}")

    # Deduplicate while preserving order.
    return list(dict.fromkeys(candidates))


def _headers(provider: str, api_key: str) -> dict[str, str]:
    headers = {
        "Accept": "application/json",
        "User-Agent": "TriHumanizer-Translator/1.6.3",
    }
    key = api_key.strip()
    if key:
        headers["Authorization"] = f"Bearer {key}"
    elif provider == "ollama":
        headers["Authorization"] = "Bearer ollama"

    if provider == "openrouter":
        headers["HTTP-Referer"] = "http://127.0.0.1"
        headers["X-Title"] = "TriHumanizer Translator"
    return headers


def _error_message(exc: urllib.error.HTTPError) -> str:
    details = exc.read().decode("utf-8", errors="replace")
    try:
        parsed = json.loads(details)
        error = parsed.get("error")
        if isinstance(error, dict):
            return redact_secrets(str(error.get("message") or error.get("detail") or details))
        return redact_secrets(str(parsed.get("message") or parsed.get("detail") or details))
    except json.JSONDecodeError:
        return redact_secrets(details or str(exc.reason))


def _read_json(request: urllib.request.Request, timeout: int) -> dict[str, Any]:
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError:
        raise
    except urllib.error.URLError as exc:
        raise LLMError(
            f"Could not connect to the provider: {exc.reason}. "
            "Check that the local service is running and the endpoint is correct."
        ) from exc
    except TimeoutError as exc:
        raise LLMError("The provider did not respond before the timeout.") from exc

    try:
        value = json.loads(body)
    except json.JSONDecodeError as exc:
        raise LLMError("Provider returned a non-JSON HTTP response.") from exc
    if not isinstance(value, dict):
        raise LLMError("Provider returned an unexpected JSON response.")
    return value


def _require_key(provider: str, api_key: str) -> None:
    spec = PROVIDER_DEFAULTS.get(provider, {})
    if spec.get("requires_key") and not api_key.strip():
        raise LLMError("This provider requires an API key.")


def _parse_models(data: dict[str, Any]) -> list[str]:
    raw_models: Any = data.get("data")
    if raw_models is None:
        raw_models = data.get("models")
    if raw_models is None:
        raw_models = data.get("items")

    models: list[str] = []
    if isinstance(raw_models, list):
        for item in raw_models:
            model_id = ""
            if isinstance(item, str):
                model_id = item
            elif isinstance(item, dict):
                model_id = str(
                    item.get("id")
                    or item.get("name")
                    or item.get("model")
                    or item.get("model_id")
                    or ""
                )
            model_id = model_id.strip()
            if model_id:
                models.append(model_id)

    return sorted(set(models), key=str.casefold)


def list_models(
    *,
    provider: str,
    api_key: str,
    custom_url: str = "",
    timeout: int = 20,
) -> tuple[list[str], str]:
    provider = provider.strip().lower()
    _require_key(provider, api_key)
    base = _base_url(provider, custom_url)
    headers = _headers(provider, api_key)

    last_error = ""
    for endpoint in _endpoint_candidates(base, "models"):
        request = urllib.request.Request(endpoint, headers=headers, method="GET")
        try:
            data = _read_json(request, timeout)
            models = _parse_models(data)
            if not models:
                raise LLMError("The provider responded, but no model IDs were found.")
            return models, endpoint
        except urllib.error.HTTPError as exc:
            message = _error_message(exc)
            last_error = f"Provider error {exc.code}: {message[:700]}"
            if exc.code not in {404, 405}:
                raise LLMError(last_error) from exc
        except LLMError as exc:
            last_error = str(exc)
            if "no model IDs" in last_error:
                raise

    raise LLMError(last_error or "Could not load the model list.")


def chat_completion(
    *,
    provider: str,
    model: str,
    api_key: str,
    custom_url: str,
    messages: list[dict],
    temperature: float = 0.35,
    timeout: int = 120,
) -> tuple[dict[str, Any], str]:
    provider = provider.strip().lower()
    model = model.strip()
    _require_key(provider, api_key)
    base = _base_url(provider, custom_url)

    if not model:
        raise LLMError("Enter or select a model name.")

    body = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "stream": False,
    }
    encoded = json.dumps(body, ensure_ascii=False).encode("utf-8")
    headers = _headers(provider, api_key)
    headers["Content-Type"] = "application/json"

    last_error = ""
    for endpoint in _endpoint_candidates(base, "chat/completions"):
        request = urllib.request.Request(endpoint, data=encoded, headers=headers, method="POST")
        try:
            data = _read_json(request, timeout)
            return _parse_json_object(_extract_content(data)), endpoint
        except urllib.error.HTTPError as exc:
            message = _error_message(exc)
            last_error = f"Provider error {exc.code}: {message[:700]}"
            # Only retry a second path when the first path itself does not exist.
            # Retrying a completed generation on 429/500 could duplicate a request.
            if exc.code not in {404, 405}:
                raise LLMError(last_error) from exc

    raise LLMError(last_error or "Could not call the chat completion endpoint.")


def probe_model(
    *,
    provider: str,
    model: str,
    api_key: str,
    custom_url: str = "",
    timeout: int = 45,
) -> tuple[str, str, int]:
    """Send a tiny real chat request to verify the selected model.

    Unlike ``chat_completion`` this intentionally accepts plain text because the
    diagnostic request only needs to prove that the provider can invoke the
    chosen model. A few OpenAI-compatible services disagree on the token-limit
    field, so the diagnostic tolerantly retries only after a rejected request.
    """
    provider = provider.strip().lower()
    model = model.strip()
    _require_key(provider, api_key)
    base = _base_url(provider, custom_url)
    if not model:
        raise LLMError("Enter or select a model name.")

    common_body = {
        "model": model,
        "messages": [
            {"role": "system", "content": "This is a connection test. Reply with exactly: OK"},
            {"role": "user", "content": "Connection test"},
        ],
        "stream": False,
    }
    body_variants = [
        {**common_body, "temperature": 0, "max_tokens": 16},
        {**common_body, "max_completion_tokens": 16},
        common_body,
    ]
    headers = _headers(provider, api_key)
    headers["Content-Type"] = "application/json"

    started = time.perf_counter()
    last_error = ""
    for endpoint in _endpoint_candidates(base, "chat/completions"):
        endpoint_missing = False
        for body in body_variants:
            encoded = json.dumps(body, ensure_ascii=False).encode("utf-8")
            request = urllib.request.Request(endpoint, data=encoded, headers=headers, method="POST")
            try:
                data = _read_json(request, timeout)
                reply = _extract_content(data).strip()
                elapsed_ms = max(1, round((time.perf_counter() - started) * 1000))
                return reply or "OK", endpoint, elapsed_ms
            except urllib.error.HTTPError as exc:
                message = _error_message(exc)
                last_error = f"Provider error {exc.code}: {message[:700]}"
                if exc.code in {404, 405}:
                    endpoint_missing = True
                    break
                if exc.code == 400:
                    # Retry only a rejected diagnostic request with a more
                    # conservative OpenAI-compatible payload.
                    continue
                raise LLMError(last_error) from exc
        if endpoint_missing:
            continue

    raise LLMError(last_error or "Could not test the selected model.")
