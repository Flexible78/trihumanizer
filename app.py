from __future__ import annotations

import hmac
import os
import secrets
import threading
import time
from io import BytesIO
from pathlib import Path

from flask import Flask, Response, g, jsonify, render_template, request, session, send_file

from intent import classify_intent, heuristic_intent
from llm_client import LLMError, chat_completion, list_models, probe_model, redact_secrets
from pdf_export import build_results_pdf
from prompts import (
    build_improve_messages,
    build_intent_messages,
    build_messages,
    build_revision_messages,
    build_write_messages,
    INTENT_SYSTEM_PROMPT,
)
from provider_config import (
    APP_VERSION,
    PROVIDER_CATALOG,
    is_allowed_model,
    is_allowed_provider,
    public_config,
    resolve_api_key,
)
from quality import assess_result, choose_better_result
from research import research_enabled, run_research
from settings_store import (
    forget_provider,
    public_state as settings_public_state,
    remember_settings,
)
from storage import make_store

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

# Serverless filesystems (Vercel) are read-only; never attempt to create
# directories there. Local installs create data/ lazily and tolerate failures.
HOSTED = bool(os.environ.get("VERCEL") or os.environ.get("TRIHUMANIZER_HOSTED"))
if not HOSTED:
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
STORE = make_store(DATA_DIR / "history.db" if not HOSTED else None)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024
app.secret_key = os.environ.get("FLASK_SECRET_KEY") or secrets.token_hex(32)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = bool(os.environ.get("VERCEL") or os.environ.get("TRIHUMANIZER_HTTPS"))

ALLOWED_LANGUAGES = {"auto", "ru", "en", "he"}
ALLOWED_TARGETS = {"auto", "ru", "en", "he"}
ALLOWED_MODES = {"business", "friendly", "short_reply"}
ALLOWED_ACTIONS = {"auto", "translate", "write", "improve", "research"}
ALLOWED_PROVIDERS = set(PROVIDER_CATALOG)
MAX_TEXT_LENGTH = 20000

APP_PASSWORD = os.environ.get("APP_PASSWORD", "").strip()
AUTH_REQUIRED = bool(APP_PASSWORD)
PROTECTED_PREFIXES = (
    "/api/process",
    "/api/models",
    "/api/test/",
    "/api/export/",
    "/api/history",
    "/api/intent",
    "/api/research",
    "/api/control/",
    "/api/settings",
)


def _schedule_exit(code: int) -> None:
    timer = threading.Timer(0.45, lambda: os._exit(code))
    timer.daemon = True
    timer.start()


def _provider(payload: dict) -> str:
    return str(payload.get("provider") or "mistral").strip().lower()


def _resolved_key(payload: dict, provider: str) -> str:
    manual = str(payload.get("api_key") or "")
    return resolve_api_key(provider, manual)


def _remember(payload: dict, provider: str, model: str = "") -> None:
    """Persist the working provider/model/key so a restart keeps working.

    Called only after the provider accepted a request, so nothing but known
    good credentials is stored. Storage failures are ignored on purpose:
    persistence is a convenience and must never break a successful request.
    """
    if HOSTED:
        return
    try:
        remember_settings(
            provider=provider,
            model=model or str(payload.get("model") or ""),
            custom_url=str(payload.get("custom_url") or ""),
            api_key=str(payload.get("api_key") or ""),
        )
    except Exception:
        pass


def _redact_error(error: BaseException) -> str:
    return redact_secrets(str(error))[:700]


def _requires_auth() -> bool:
    return AUTH_REQUIRED and not session.get("authed")


@app.before_request
def gate_requests():
    path = request.path
    if request.method == "OPTIONS":
        return Response(status=204)
    if AUTH_REQUIRED and path.startswith(PROTECTED_PREFIXES) and not session.get("authed"):
        return jsonify({"ok": False, "error": "Authentication required."}), 401
    return None


@app.after_request
def secure_headers(response):
    response.headers["Cache-Control"] = "no-store, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Permissions-Policy"] = "microphone=(self), geolocation=(), camera=()"
    nonce = getattr(g, "csp_nonce", "")
    script_src = "'self'" + (f" 'nonce-{nonce}'" if nonce else "")
    response.headers["Content-Security-Policy"] = (
        f"default-src 'self'; script-src {script_src}; "
        "style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
        "font-src 'self' data:; connect-src 'self'; "
        "frame-ancestors 'none'; base-uri 'self'; form-action 'self'; "
        "manifest-src 'self'; worker-src 'self'"
    )
    if request.is_secure or os.environ.get("VERCEL"):
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    if request.path.startswith("/static/"):
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    return response


def _render(template: str, **context):
    nonce = secrets.token_urlsafe(16)
    g.csp_nonce = nonce
    return render_template(template, csp_nonce=nonce, **context)


@app.get("/")
def index():
    return _render("index.html", ai_config=public_config(), auth_required=AUTH_REQUIRED)


@app.get("/manifest.webmanifest")
def webmanifest():
    return app.send_static_file("manifest.webmanifest")


@app.get("/api/health")
def health():
    return jsonify({"ok": True, "version": APP_VERSION, "hosted": HOSTED, "auth_required": AUTH_REQUIRED})


@app.get("/api/config")
def config():
    return jsonify({"ok": True, **public_config()})


@app.post("/api/auth/login")
def login():
    if not AUTH_REQUIRED:
        return jsonify({"ok": False, "error": "Authentication is not enabled."}), 403
    payload = request.get_json(silent=True) or {}
    password = str(payload.get("password") or "")
    if hmac.compare_digest(password, APP_PASSWORD):
        session["authed"] = True
        session.permanent = False
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "Incorrect password."}), 401


@app.post("/api/auth/logout")
def logout():
    session.clear()
    return jsonify({"ok": True})


@app.get("/api/settings")
def read_saved_settings():
    """Return the stored selection without ever exposing the API key."""
    return jsonify({"ok": True, "settings": settings_public_state()})


@app.post("/api/settings")
def save_settings():
    """Store provider, model, endpoint and key for the next application start.

    The key is written to data/settings.json on the server. The response only
    reports whether a key is on file, never the key itself.
    """
    if HOSTED:
        return jsonify(
            {
                "ok": False,
                "error": "This deployment has a read-only filesystem; use environment variables.",
                "settings": settings_public_state(),
            }
        ), 400

    payload = request.get_json(silent=True) or {}
    provider = _provider(payload)
    if provider not in ALLOWED_PROVIDERS:
        return jsonify({"ok": False, "error": "Invalid provider."}), 400

    model = str(payload.get("model") or "").strip()
    if model and not is_allowed_model(model):
        return jsonify({"ok": False, "error": "Invalid model name."}), 400

    custom_url = str(payload.get("custom_url") or "").strip()
    if custom_url and not custom_url.startswith(("http://", "https://")):
        return jsonify({"ok": False, "error": "Endpoint must start with http:// or https://."}), 400

    stored = remember_settings(
        provider=provider,
        model=model,
        custom_url=custom_url,
        api_key=str(payload.get("api_key") or ""),
        clear_key=bool(payload.get("clear_key")),
    )
    return jsonify({"ok": True, "stored": stored, "settings": settings_public_state()})


@app.delete("/api/settings")
def delete_settings():
    """Forget everything stored for one provider, including its API key."""
    payload = request.get_json(silent=True) or {}
    provider = str(payload.get("provider") or request.args.get("provider") or "").strip().lower()
    if provider not in ALLOWED_PROVIDERS:
        return jsonify({"ok": False, "error": "Invalid provider."}), 400
    forget_provider(provider)
    return jsonify({"ok": True, "settings": settings_public_state()})


@app.post("/api/models")
def models():
    payload = request.get_json(silent=True) or {}
    provider = _provider(payload)
    if provider not in ALLOWED_PROVIDERS:
        return jsonify({"ok": False, "error": "Invalid provider."}), 400

    try:
        items, endpoint = list_models(
            provider=provider,
            api_key=_resolved_key(payload, provider),
            custom_url=str(payload.get("custom_url") or ""),
        )
    except LLMError as exc:
        return jsonify({"ok": False, "error": _redact_error(exc)}), 502

    _remember(payload, provider)
    return jsonify({"ok": True, "models": items, "endpoint": endpoint})


@app.post("/api/test/key")
def test_api_key():
    payload = request.get_json(silent=True) or {}
    provider = _provider(payload)
    if provider not in ALLOWED_PROVIDERS:
        return jsonify({"ok": False, "error": "Invalid provider."}), 400

    started = time.perf_counter()
    error_category = None
    try:
        items, endpoint = list_models(
            provider=provider,
            api_key=_resolved_key(payload, provider),
            custom_url=str(payload.get("custom_url") or ""),
            timeout=25,
        )
    except LLMError as exc:
        error_category = _error_category(str(exc))
        return jsonify(
            {
                "ok": False,
                "error": _redact_error(exc),
                "endpoint_reachable": error_category not in {"connection", "timeout"},
                "key_accepted": False,
                "error_category": error_category,
                "elapsed_ms": max(1, round((time.perf_counter() - started) * 1000)),
            }
        ), 502

    _remember(payload, provider)
    return jsonify(
        {
            "ok": True,
            "provider": provider,
            "endpoint": endpoint,
            "models_count": len(items),
            "sample_models": items[:5],
            "endpoint_reachable": True,
            "key_accepted": True,
            "error_category": None,
            "elapsed_ms": max(1, round((time.perf_counter() - started) * 1000)),
        }
    )


def _error_category(message: str) -> str:
    lowered = message.casefold()
    if "connect" in lowered or "urlopen" in lowered:
        return "connection"
    if "timeout" in lowered:
        return "timeout"
    if "401" in lowered or "unauthorized" in lowered or "invalid api key" in lowered:
        return "auth"
    if "403" in lowered or "forbidden" in lowered:
        return "forbidden"
    if "404" in lowered or "not found" in lowered:
        return "endpoint_not_found"
    if "429" in lowered or "rate" in lowered:
        return "rate_limit"
    if "model" in lowered and ("not found" in lowered or "does not exist" in lowered):
        return "model_unavailable"
    return "provider"


@app.post("/api/test/model")
def test_selected_model():
    payload = request.get_json(silent=True) or {}
    provider = _provider(payload)
    model = str(payload.get("model") or "").strip()
    if provider not in ALLOWED_PROVIDERS:
        return jsonify({"ok": False, "error": "Invalid provider."}), 400
    if not model:
        return jsonify({"ok": False, "error": "Select a model to test."}), 400
    if not is_allowed_model(model):
        return jsonify({"ok": False, "error": "Invalid model name."}), 400

    try:
        reply, endpoint, elapsed_ms = probe_model(
            provider=provider,
            model=model,
            api_key=_resolved_key(payload, provider),
            custom_url=str(payload.get("custom_url") or ""),
        )
    except LLMError as exc:
        return jsonify(
            {
                "ok": False,
                "error": _redact_error(exc),
                "error_category": _error_category(str(exc)),
            }
        ), 502

    _remember(payload, provider, model)
    return jsonify(
        {
            "ok": True,
            "provider": provider,
            "model": model,
            "endpoint": endpoint,
            "reply": redact_secrets(reply)[:180],
            "elapsed_ms": elapsed_ms,
            "error_category": None,
        }
    )


def _validate_process_payload(payload: dict):
    text = str(payload.get("text") or "").strip()
    if not text:
        return "Enter or paste text."
    if len(text) > MAX_TEXT_LENGTH:
        return f"Maximum length is {MAX_TEXT_LENGTH:,} characters."

    source = str(payload.get("source_language") or "auto")
    target = str(payload.get("target_language") or "en")
    mode = str(payload.get("mode") or "business")
    action = str(payload.get("action") or "translate")
    provider = _provider(payload)
    model = str(payload.get("model") or "").strip()

    if source not in ALLOWED_LANGUAGES:
        return "Invalid source language."
    if target not in ALLOWED_TARGETS:
        return "Invalid target language."
    if mode not in ALLOWED_MODES:
        return "Invalid mode."
    if action not in ALLOWED_ACTIONS:
        return "Invalid action."
    if provider not in ALLOWED_PROVIDERS:
        return "Invalid provider."
    if model and not is_allowed_model(model):
        return "Invalid model name."
    return None


@app.post("/api/intent")
def detect_intent():
    payload = request.get_json(silent=True) or {}
    text = str(payload.get("text") or "").strip()
    if not text:
        return jsonify({"ok": False, "error": "Enter a request."}), 400
    provider = _provider(payload)
    if provider not in ALLOWED_PROVIDERS:
        return jsonify({"ok": False, "error": "Invalid provider."}), 400

    model = str(payload.get("model") or "").strip()
    heuristic = heuristic_intent(text, str(payload.get("source_language") or "auto"))
    if model and heuristic["mode"] == "translate" and not heuristic["needs_live_research"]:
        try:
            contract = classify_intent(
                text=text,
                source_language=str(payload.get("source_language") or "auto"),
                provider=provider,
                model=model,
                api_key=_resolved_key(payload, provider),
                custom_url=str(payload.get("custom_url") or ""),
                intent_system_prompt=INTENT_SYSTEM_PROMPT,
            )
            return jsonify({"ok": True, "intent": contract, "source": "model"})
        except LLMError:
            pass
    return jsonify({"ok": True, "intent": heuristic, "source": "heuristic"})


@app.post("/api/process")
def process_text():
    payload = request.get_json(silent=True) or {}
    validation_error = _validate_process_payload(payload)
    if validation_error:
        return jsonify({"ok": False, "error": validation_error}), 400

    text = str(payload.get("text") or "").strip()
    provider = _provider(payload)
    model = str(payload.get("model") or "").strip()
    action = str(payload.get("action") or "translate")
    api_key = _resolved_key(payload, provider)
    custom_url = str(payload.get("custom_url") or "")
    tone = str(payload.get("mode") or "business")
    tone_temperature = {"business": 0.22, "friendly": 0.45, "short_reply": 0.28}.get(tone, 0.30)

    intent = None
    if action == "auto":
        intent = heuristic_intent(text, str(payload.get("source_language") or "auto"))
        action = intent["mode"]

    try:
        if action in {"translate", "improve"}:
            if action == "improve":
                messages = build_improve_messages(payload, intent)
                result, endpoint = chat_completion(
                    provider=provider,
                    model=model,
                    api_key=api_key,
                    custom_url=custom_url,
                    messages=messages,
                    temperature=0.30,
                )
            else:
                result, endpoint = chat_completion(
                    provider=provider,
                    model=model,
                    api_key=api_key,
                    custom_url=custom_url,
                    messages=build_messages(payload),
                    temperature=tone_temperature,
                )
                quality_reasons = assess_result(payload, result)
                quality_retry = False
                if quality_reasons:
                    quality_retry = True
                    try:
                        second_result, second_endpoint = chat_completion(
                            provider=provider,
                            model=model,
                            api_key=api_key,
                            custom_url=custom_url,
                            messages=build_revision_messages(payload, result, quality_reasons),
                            temperature=max(0.18, tone_temperature - 0.04),
                        )
                        result = choose_better_result(payload, result, second_result)
                        endpoint = second_endpoint
                    except LLMError:
                        pass
                result["quality_retry"] = quality_retry
        elif action == "write":
            if research_enabled() and (intent or {}).get("needs_live_research"):
                try:
                    findings = run_research(
                        text,
                        provider=str(os.environ.get("RESEARCH_PROVIDER", "") or ""),
                        model=str(os.environ.get("RESEARCH_MODEL", "") or ""),
                        api_key=str(os.environ.get("RESEARCH_API_KEY", "") or ""),
                        base_url=str(os.environ.get("RESEARCH_BASE_URL", "") or ""),
                    )
                    payload["research_findings"] = findings.get("verified_findings") or []
                    payload["research_sources"] = findings.get("sources") or []
                except LLMError as exc:
                    result = {
                        "detected_language": "unknown",
                        "subject": "",
                        "greeting": "",
                        "body": "",
                        "closing": "",
                        "missing_information": ["live research unavailable"],
                        "verified_findings": [],
                        "sources": [],
                        "notes": f"Live research failed: {_redact_error(exc)}",
                    }
                    return jsonify(
                        {
                            "ok": True,
                            "result": result,
                            "provider": provider,
                            "model": model,
                            "endpoint": "",
                            "intent": intent,
                            "quality_retry": False,
                            "quality_warnings": [],
                        }
                    )
            messages = build_write_messages(payload, intent)
            result, endpoint = chat_completion(
                provider=provider,
                model=model,
                api_key=api_key,
                custom_url=custom_url,
                messages=messages,
                temperature=0.45,
            )
        elif action == "clarify":
            # The intent resolver detected a request that is missing the actual
            # text to work with. Respond without calling the model and let the
            # UI ask the user for the missing piece instead of erroring.
            missing = (intent or {}).get("missing_information") or ["text_to_process"]
            result = {
                "detected_language": (intent or {}).get("input_language", "unknown"),
                "humanized_original": "",
                "literal_translation": "",
                "humanized_translation": "",
                "subject": "",
                "greeting": "",
                "body": "",
                "closing": "",
                "answer": "",
                "missing_information": missing,
                "verified_findings": [],
                "sources": [],
                "notes": "I need the actual text to work with. Enter the text you want translated or improved, or describe in more detail the text you want written.",
            }
            endpoint = ""
        elif action == "research":
            if not research_enabled():
                return jsonify(
                    {
                        "ok": True,
                        "result": {
                            "detected_language": "unknown",
                            "answer": "",
                            "subject": "",
                            "greeting": "",
                            "body": "",
                            "closing": "",
                            "missing_information": [
                                "Live research is not enabled on this server. Provide the store URL or current facts to continue."
                            ],
                            "verified_findings": [],
                            "sources": [],
                            "notes": "Live research is disabled. No current facts were fabricated.",
                        },
                        "provider": provider,
                        "model": model,
                        "endpoint": "",
                        "intent": intent,
                        "quality_retry": False,
                        "quality_warnings": [],
                    }
                )
            findings = run_research(
                text,
                provider=str(os.environ.get("RESEARCH_PROVIDER", "") or ""),
                model=str(os.environ.get("RESEARCH_MODEL", "") or ""),
                api_key=str(os.environ.get("RESEARCH_API_KEY", "") or ""),
                base_url=str(os.environ.get("RESEARCH_BASE_URL", "") or ""),
            )
            result = {
                "detected_language": "unknown",
                "answer": findings.get("answer") or "",
                "subject": "",
                "greeting": "",
                "body": "",
                "closing": "",
                "missing_information": findings.get("needs_user_input") or [],
                "verified_findings": findings.get("verified_findings") or [],
                "sources": findings.get("sources") or [],
                "notes": findings.get("notes") or "",
                "retrieved_at": findings.get("retrieved_at") or "",
            }
            endpoint = ""
    except (LLMError, ValueError) as exc:
        return jsonify(
            {"ok": False, "error": _redact_error(exc), "error_category": _error_category(str(exc))}
        ), 502

    _remember(payload, provider, model)

    # Clarify results are informational only and would only add empty history noise.
    history_id = None if action == "clarify" else STORE.add(payload, result)

    return jsonify(
        {
            "ok": True,
            "history_id": history_id,
            "result": result,
            "provider": provider,
            "model": model,
            "endpoint": endpoint or "",
            "intent": intent,
            "action": action,
            "quality_retry": bool(result.get("quality_retry")),
            "quality_warnings": [],
        }
    )


@app.post("/api/export/pdf")
def export_pdf():
    payload = request.get_json(silent=True) or {}
    try:
        pdf_bytes = build_results_pdf(payload)
    except Exception as exc:
        return jsonify({"ok": False, "error": f"Could not create the PDF: {_redact_error(exc)}"}), 500
    return send_file(
        BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name="TriHumanizer_result.pdf",
    )


@app.get("/api/history")
def history():
    if HOSTED:
        return jsonify({"ok": True, "items": []})
    return jsonify({"ok": True, "items": STORE.list()})


@app.delete("/api/history/<int:history_id>")
def delete_history_item(history_id: int):
    if HOSTED:
        return jsonify({"ok": True, "deleted": True})
    deleted = STORE.delete(history_id)
    return jsonify({"ok": True, "deleted": deleted})


@app.delete("/api/history")
def clear_history():
    if not HOSTED:
        STORE.clear()
    return jsonify({"ok": True})


@app.post("/api/control/restart")
def restart_application():
    _schedule_exit(75)
    return jsonify({"ok": True, "message": "Restart started."})


@app.post("/api/control/exit")
def exit_application():
    _schedule_exit(0)
    return jsonify({"ok": True, "message": "Application stopped."})


if __name__ == "__main__":
    port = int(os.environ.get("TRIHUMANIZER_PORT", "8868"))
    app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)
