"""Smart intent classification tests (heuristic path; no paid requests)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import intent as intent_module  # noqa: E402
from intent import classify_intent, heuristic_intent, parse_contract  # noqa: E402


def test_literal_translation() -> None:
    intent = heuristic_intent("ghbdtn rfr ndjb ltkf")
    assert intent["mode"] == "translate", intent
    assert intent["input_language"] in {"en", "ru"}, intent


def test_rewrite_request() -> None:
    intent = heuristic_intent("Make this sound more natural and professional")
    assert intent["mode"] == "improve", intent


def test_email_creation() -> None:
    request = (
        "Compose an email to optical store support asking to exchange my glasses, "
        "find out the store opening hours, and ask whether the required model is in stock"
    )
    intent = heuristic_intent(request)
    assert intent["mode"] == "write", intent
    assert intent["requested_format"] == "email", intent
    assert intent["needs_live_research"] is True, intent


def test_research_request() -> None:
    intent = heuristic_intent("What are the opening hours of the optical store near me?")
    assert intent["mode"] == "research", intent
    assert intent["needs_live_research"] is True, intent


def test_missing_store_details() -> None:
    request = "Check whether model ABC is in stock"
    intent = heuristic_intent(request)
    assert intent["mode"] == "research", intent
    assert "store_or_url" in intent["missing_information"], intent


def test_no_fabricated_facts() -> None:
    # Requests asking for hours/stock must carry the research flag so the
    # server never silently invents facts.
    for request in [
        "What time does the store close today?",
        "Is the glasses model ABC available in your shop?",
        "Сколько стоят линзы в оптике?",
        "האם הדגם במלאי בחנות?",
    ]:
        intent = heuristic_intent(request)
        assert intent["needs_live_research"] is True, (request, intent)


def test_clarify_missing_text() -> None:
    # A bare instruction with no actual content must be flagged as "clarify"
    # and carry the missing-information marker, never crash the process route.
    intent = heuristic_intent("Translate this")
    assert intent["mode"] == "clarify", intent
    assert "text_to_process" in intent["missing_information"], intent

    intent = heuristic_intent("переведи это")
    assert intent["mode"] == "clarify", intent


def test_classify_intent_uses_model_contract() -> None:
    # Regression: classify_intent used to pass the plain-text cleaned_request
    # string to parse_contract (raising LLMError and silently falling back to
    # the heuristic). The model's parsed JSON object must be re-serialized.
    contract = {
        "mode": "write",
        "input_language": "en",
        "output_language": "en",
        "needs_live_research": True,
        "missing_information": ["store name"],
        "cleaned_request": "compose email",
        "requested_format": "email",
        "requested_tone": "polite",
    }

    original = intent_module.chat_completion
    intent_module.chat_completion = lambda **kwargs: (contract, "endpoint")
    try:
        result = classify_intent(
            text="Translate this long passage of text that has many words exceeding the limit so the heuristic short-circuit does not trigger and we reach the model call for classification",
            source_language="auto",
            provider="mistral",
            model="mistral-large-latest",
            api_key="",
            custom_url="",
            intent_system_prompt="classify",
        )
    finally:
        intent_module.chat_completion = original

    assert result["mode"] == "write", result
    assert result["requested_format"] == "email", result
    assert result["missing_information"] == ["store name"], result


def test_parse_contract() -> None:
    raw = """
    ```json
    {"mode": "write", "input_language": "en", "output_language": "en",
     "needs_live_research": true, "missing_information": ["store name"],
     "cleaned_request": "compose email", "requested_format": "email",
     "requested_tone": "polite"}
    ```
    """
    contract = parse_contract(raw)
    assert contract["mode"] == "write"
    assert contract["requested_format"] == "email"
    assert contract["needs_live_research"] is True
    assert contract["missing_information"] == ["store name"]


def test_parse_contract_invalid_mode() -> None:
    contract = parse_contract('{"mode": "hack", "input_language": "en"}')
    assert contract["mode"] == "translate", contract


if __name__ == "__main__":
    test_literal_translation()
    test_rewrite_request()
    test_email_creation()
    test_research_request()
    test_missing_store_details()
    test_no_fabricated_facts()
    test_clarify_missing_text()
    test_classify_intent_uses_model_contract()
    test_parse_contract()
    test_parse_contract_invalid_mode()
    print("INTENT TESTS OK")
