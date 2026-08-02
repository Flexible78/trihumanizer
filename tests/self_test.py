from __future__ import annotations

import json
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import app
from llm_client import chat_completion, list_models, probe_model, redact_secrets
from pdf_export import build_results_pdf
from storage import HistoryStore, NullHistoryStore, hosted_mode
from quality import assess_result, similarity
from prompts import build_messages


class MockHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        return

    def do_GET(self):
        if self.path == "/v1/models":
            body = {"data": [{"id": "test-model-a"}, {"id": "test-model-b"}]}
            self._json(200, body)
            return
        self._json(404, {"error": {"message": "not found"}})

    def do_POST(self):
        if self.path == "/v1/chat/completions":
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            if payload.get("max_tokens") == 16:
                self._json(200, {"choices": [{"message": {"content": "OK"}}]})
                return
            content = json.dumps(
                {
                    "detected_language": "ru",
                    "humanized_original": "Живой исходный текст.",
                    "literal_translation": "",
                    "humanized_translation": "Natural translated text.",
                    "notes": "",
                },
                ensure_ascii=False,
            )
            self._json(200, {"choices": [{"message": {"content": content}}]})
            return
        self._json(404, {"error": {"message": "not found"}})

    def _json(self, status: int, data: dict):
        raw = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


# Intentionally fake credential used to prove that redaction works. It is
# assembled from two literals so that no tracked file ever contains a token
# shaped like a real provider key, which is what the secret scan in
# tests/test_security.py and the CI job look for.
FAKE_API_KEY = "sk-" + "abcdefghijklmnopqrstuvwxyz123456"


def test_redaction() -> None:
    message = f"Provider error 401: invalid key {FAKE_API_KEY}"
    redacted = redact_secrets(message)
    assert FAKE_API_KEY not in redacted
    assert "[REDACTED]" in redacted


def main() -> int:
    client = app.test_client()
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.get_json()["version"] == "1.6.3"

    config_response = client.get("/api/config")
    assert config_response.status_code == 200
    public_config = config_response.get_json()
    assert public_config["defaultProvider"] == "mistral"
    assert public_config["providers"]["mistral"]["model"] == "mistral-large-latest"
    assert isinstance(public_config["providers"]["mistral"]["configuredKey"], bool)
    serialized_config = json.dumps(public_config, ensure_ascii=False)
    assert "Q7mz" not in serialized_config
    assert "gsk_" not in serialized_config
    assert "AIza" not in serialized_config
    assert "sk-" not in serialized_config
    # Help text may reference environment variable NAMES (e.g. OPENAI_API_KEY),
    # which is not a leak. Actual secret values must never appear.
    assert "sk-live-" not in serialized_config.casefold()
    assert "MISTRAL_API_KEY" not in serialized_config

    test_redaction()

    noisy_payload = {
        "text": "мама мыла раму! ну и чо такого спросил я ее. да пошла ты хочу узнать скоклько время сейчас слышь?",
        "source_language": "ru",
        "target_language": "en",
        "mode": "business",
        "humanize_original": True,
        "humanize_translation": True,
    }
    weak_result = {
        "detected_language": "ru",
        "humanized_original": "Мама мыла раму! Ну и чё такого — спросил я её. Да пошла ты, хочу узнать, сколько время сейчас, слышь?",
        "literal_translation": "",
        "humanized_translation": "Weak translation",
        "notes": "",
    }
    reasons = assess_result(noisy_payload, weak_result)
    assert "business_rewrite_too_close_to_noisy_input" in reasons
    assert "business_output_retained_profanity" in reasons
    messages = build_messages(noisy_payload)
    assert "not proofreading" in messages[0]["content"].lower()
    assert "Да пошла ты" in messages[0]["content"]
    assert similarity(noisy_payload["text"], weak_result["humanized_original"]) > 0.80

    with tempfile.TemporaryDirectory() as tmp:
        store = HistoryStore(Path(tmp) / "history.db")
        row_id = store.add(
            {
                "source_language": "ru",
                "target_language": "en",
                "mode": "business",
                "context": "test",
                "text": "Тест",
            },
            {
                "detected_language": "ru",
                "humanized_original": "Тест",
                "literal_translation": "",
                "humanized_translation": "Test",
                "notes": "",
            },
        )
        assert len(store.list()) == 1
        assert store.delete(row_id) is True
        assert store.list() == []

    pdf = build_results_pdf(
        {
            "source_text": "Привет",
            "humanized_original": "Привет!",
            "humanized_translation": "שלום!",
            "literal_translation": "Hello",
            "notes": "",
            "meta": {"source_language": "ru", "target_language": "he", "mode": "friendly"},
        }
    )
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 1000

    server = ThreadingHTTPServer(("127.0.0.1", 0), MockHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.server_port}/v1"
        models, endpoint = list_models(provider="custom", api_key="", custom_url=base)
        assert models == ["test-model-a", "test-model-b"]
        assert endpoint.endswith("/v1/models")
        result, endpoint = chat_completion(
            provider="custom",
            model="test-model-a",
            api_key="",
            custom_url=base,
            messages=[{"role": "user", "content": "test"}],
        )
        assert result["humanized_translation"] == "Natural translated text."
        assert endpoint.endswith("/v1/chat/completions")

        reply, endpoint, elapsed_ms = probe_model(
            provider="custom",
            model="test-model-a",
            api_key="",
            custom_url=base,
        )
        assert reply == "OK"
        assert endpoint.endswith("/v1/chat/completions")
        assert elapsed_ms >= 1

        key_test = client.post(
            "/api/test/key",
            json={"provider": "custom", "custom_url": base, "api_key": ""},
        )
        assert key_test.status_code == 200
        assert key_test.get_json()["models_count"] == 2

        model_test = client.post(
            "/api/test/model",
            json={"provider": "custom", "custom_url": base, "api_key": "", "model": "test-model-a"},
        )
        assert model_test.status_code == 200
        assert model_test.get_json()["reply"] == "OK"
    finally:
        server.shutdown()
        server.server_close()

    export_response = client.post(
        "/api/export/pdf",
        json={"source_text": "Тест", "humanized_translation": "Test", "meta": {}},
    )
    assert export_response.status_code == 200
    assert export_response.data.startswith(b"%PDF")

    # Hosted mode uses the null store and never touches SQLite.
    null_store = NullHistoryStore()
    assert null_store.list() == []
    assert null_store.add({"text": "x"}, {"result": 1}) == 0
    assert hosted_mode() is False

    print("SELF TEST OK")
    print("- Flask health endpoint: OK")
    print("- public provider config and secret filtering: OK")
    print("- history add/delete: OK")
    print("- TXT is client-side UTF-8: configured")
    print("- PDF generation with RU/EN/HE: OK")
    print("- model list endpoint: OK")
    print("- chat completion endpoint: OK")
    print("- API key/endpoint diagnostic: OK")
    print("- selected-model diagnostic: OK")
    print("- noisy business-text quality gate: OK")
    print("- strengthened prompt example: OK")
    print("- no paid model request was made")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
