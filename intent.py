"""Smart request mode: classify natural-language user requests.

Produces a structured intent contract:

{
  "mode": "translate | write | improve | research | clarify",
  "input_language": "ru | en | he | unknown",
  "output_language": "ru | en | he",
  "needs_live_research": true,
  "missing_information": [],
  "cleaned_request": "",
  "requested_format": "email | message | letter | post | plain_text | other",
  "requested_tone": "neutral | polite | formal | friendly | concise"
}
"""
from __future__ import annotations

import json
import re
from typing import Any

from llm_client import LLMError, chat_completion

# Fast heuristic signals used to avoid an expensive classification call when the
# intent is obvious from the wording.
_TRANSLATE_SIGNALS = (
    "translate", "translation", "переведи", "перевод", "перевести",
    "תרגם", "תרגום", "переклади", "перекласти",
)
_IMPROVE_SIGNALS = (
    "improve", "rewrite", "make this sound", "more natural", "polish",
    "улучши", "перепиши", "сделай естественнее", "исправь",
    "שפר", "שכתב", "תעשה את זה טבעי",
)
_WRITE_SIGNALS = (
    "write", "compose", "create", "draft", "generate", "make a",
    "напиши", "составь", "создай", "сочини",
    "כתוב", "צור", "נסח",
)
_RESEARCH_SIGNALS = (
    "research", "search", "find", "opening hours", "in stock", "available",
    "what time", "what are the hours", "when does", "close today", "closes",
    "how much", "price of", "is it open", "open now", "opening time",
    "исследуй", "найди", "поищи", "часы работы", "в наличии", "актуально",
    "сколько", "когда открыт", "во сколько", "закрывается", "почём", "цена",
    "חקור", "חפש", "שעות פתיחה", "במלאי", "מחיר", "מתי נפתח", "כמה עולה",
)

_FORMAT_SIGNALS = {
    "email": ("email", "e-mail", "письмо", "email", "דוא\"ל", "מייל"),
    "letter": ("letter", "письмо", "обращение", "מכתב"),
    "post": ("post", "соцсети", "пост", "פוסט"),
    "message": ("message", "reply", "sms", "сообщение", "ответ", "הודעה", "תשובה"),
    "linkedin": ("linkedin", "профиль", "линкедин"),
}

_TONE_SIGNALS = {
    "polite": ("polite", "kindly", "please", "вежлив", "пожалуйста", "אדיב"),
    "formal": ("formal", "official", "официальн", "офиц", "רשמי"),
    "friendly": ("friendly", "warm", "дружелюбн", "тепл", "ידידותי"),
    "concise": ("concise", "short", "brief", "кратк", "коротк", "קצר"),
}


def _has(text: str, signals) -> bool:
    lower = text.casefold()
    return any(signal in lower for signal in signals)


def _guess_language(text: str) -> str:
    hebrew = re.search(r"[\u0590-\u05ff]", text)
    cyrillic = re.search(r"[А-Яа-яЁё]", text)
    if hebrew and not cyrillic:
        return "he"
    if cyrillic and not hebrew:
        return "ru"
    if cyrillic and hebrew:
        return "unknown"
    return "en"


def _guess_format(text: str) -> str:
    lower = text.casefold()
    best = "plain_text"
    best_score = 0
    for fmt, signals in _FORMAT_SIGNALS.items():
        score = sum(1 for signal in signals if signal in lower)
        if score > best_score:
            best, best_score = fmt, score
    return best


def _guess_tone(text: str) -> str:
    lower = text.casefold()
    best = "neutral"
    best_score = 0
    for tone, signals in _TONE_SIGNALS.items():
        score = sum(1 for signal in signals if signal in lower)
        if score > best_score:
            best, best_score = tone, score
    return best


def heuristic_intent(text: str, source_language: str = "auto") -> dict[str, Any]:
    """Fast local intent guess. Returns a partial contract (no LLM call)."""
    text = (text or "").strip()
    lower = text.casefold()

    needs_research = _has(lower, _RESEARCH_SIGNALS)
    missing: list[str] = []
    if needs_research and any(token in lower for token in ("hours", "stock", "price", "open", "available", "часы", "наличи", "цены", "שעות", "מלאי")):
        if not re.search(r"(?:store|shop|site|url|link|branch)", lower):
            missing.append("store_or_url")

    mode = "translate"
    if _has(lower, _TRANSLATE_SIGNALS):
        mode = "translate"
    elif _has(lower, _IMPROVE_SIGNALS):
        mode = "improve"
    elif _has(lower, _WRITE_SIGNALS) and len(text.split()) >= 3:
        mode = "write"
    elif needs_research:
        mode = "research"

    # A bare instruction like "translate this" or "переведи это" with no
    # actual content to work with is a request missing essential information.
    if mode in {"translate", "improve"} and len(text.split()) <= 6 and _has(
        lower, _TRANSLATE_SIGNALS + _IMPROVE_SIGNALS + ("this", "это", "זה", "текст", "text", "message", "сообщение", "הודעה")
    ):
        if not _has(lower, ("\"", "“", "«")) and len(text.split()) <= 4:
            mode = "clarify"
            missing.append("text_to_process")

    input_language = _guess_language(text)
    output_language = input_language if input_language in {"ru", "en", "he"} else "en"

    return {
        "mode": mode,
        "input_language": input_language,
        "output_language": output_language,
        "needs_live_research": needs_research,
        "missing_information": missing,
        "cleaned_request": text,
        "requested_format": _guess_format(text),
        "requested_tone": _guess_tone(text),
    }


def parse_contract(content: str) -> dict[str, Any]:
    """Parse the model's JSON contract tolerantly."""
    raw = content.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
    raw = re.sub(r"\s*```$", "", raw)
    first = raw.find("{")
    last = raw.rfind("}")
    if first >= 0 and last > first:
        raw = raw[first : last + 1]
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LLMError("The model did not return a valid intent description.") from exc
    if not isinstance(value, dict):
        raise LLMError("The model returned an unexpected intent format.")

    allowed_modes = {"translate", "write", "improve", "research", "clarify"}
    allowed_langs = {"ru", "en", "he", "unknown"}
    mode = str(value.get("mode", "translate")).strip().lower()
    if mode not in allowed_modes:
        mode = "translate"
    input_language = str(value.get("input_language", "unknown")).strip().lower()
    if input_language not in allowed_langs:
        input_language = "unknown"
    output_language = str(value.get("output_language", "en")).strip().lower()
    if output_language not in {"ru", "en", "he"}:
        output_language = "en"

    missing = value.get("missing_information") or []
    if not isinstance(missing, list):
        missing = [str(missing)]
    missing = [str(item) for item in missing if str(item).strip()][:8]

    return {
        "mode": mode,
        "input_language": input_language,
        "output_language": output_language,
        "needs_live_research": bool(value.get("needs_live_research")),
        "missing_information": missing,
        "cleaned_request": str(value.get("cleaned_request") or "").strip()[:4000],
        "requested_format": str(value.get("requested_format") or "plain_text").strip()[:30],
        "requested_tone": str(value.get("requested_tone") or "neutral").strip()[:30],
    }


def classify_intent(
    *,
    text: str,
    source_language: str = "auto",
    provider: str = "mistral",
    model: str = "",
    api_key: str = "",
    custom_url: str = "",
    intent_system_prompt: str,
) -> dict[str, Any]:
    """Determine the intent. Tries the local heuristic first and only calls the
    model when the heuristic is not conclusive (Auto mode still performs one
    model call for the actual generation in almost every case)."""
    heuristic = heuristic_intent(text, source_language)
    if heuristic["mode"] != "translate" or heuristic["needs_live_research"]:
        return heuristic

    # A plain block of text with no instruction words is a literal translation.
    words = re.findall(r"\w+", text, flags=re.UNICODE)
    if words and len(words) <= 12 and not _has(text, (_WRITE_SIGNALS + _TRANSLATE_SIGNALS)):
        heuristic["mode"] = "translate"
        return heuristic

    messages = [
        {"role": "system", "content": intent_system_prompt},
        {"role": "user", "content": f"<USER_REQUEST>\n{text[:4000]}\n</USER_REQUEST>"},
    ]
    result, _ = chat_completion(
        provider=provider,
        model=model,
        api_key=api_key,
        custom_url=custom_url,
        messages=messages,
        temperature=0.0,
        timeout=60,
    )
    # chat_completion already parses the model's JSON object; validate it through
    # parse_contract instead of re-parsing a plain string as JSON.
    contract = parse_contract(json.dumps(result, ensure_ascii=False))
    if not contract["cleaned_request"]:
        contract["cleaned_request"] = text
    return contract
