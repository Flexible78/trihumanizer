from __future__ import annotations

import re
from difflib import SequenceMatcher

RU_NOISE = {
    "чо", "чё", "че", "слышь", "скоклько", "скока", "щас", "че-то", "чето",
    "кароче", "короч", "блин", "нахрен", "пофиг", "фигня", "типа", "ваще",
}
EN_NOISE = {"gonna", "wanna", "ain't", "wtf", "dunno", "kinda", "sorta"}
HE_NOISE = {"כאילו", "יאללה", "סתם", "נו", "מה הקטע"}

RU_PROFANITY_PATTERNS = [
    r"\bпошл[аи]\b", r"\bиди\s+на\b", r"\bнах(?:уй|рен)\b", r"\bсука\b",
    r"\bбляд\w*\b", r"\bхер\w*\b", r"\bеб\w*\b", r"\bёб\w*\b",
]
EN_PROFANITY_PATTERNS = [r"\bfuck\w*\b", r"\bshit\w*\b", r"\bbitch\w*\b", r"\basshole\w*\b"]
HE_PROFANITY_PATTERNS = [r"לך\s+לעזאזל", r"בן\s+זונה", r"כוס\s+אמק"]


def _norm(text: str) -> str:
    text = text.casefold().replace("ё", "е")
    text = re.sub(r"[^\w\u0590-\u05ff]+", " ", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()


def _words(text: str) -> list[str]:
    return re.findall(r"[\w\u0590-\u05ff'-]+", text.casefold(), flags=re.UNICODE)


def similarity(a: str, b: str) -> float:
    na, nb = _norm(a), _norm(b)
    if not na and not nb:
        return 1.0
    if not na or not nb:
        return 0.0
    return SequenceMatcher(None, na, nb).ratio()


def _contains_pattern(text: str, patterns: list[str]) -> bool:
    return any(re.search(pattern, text, flags=re.IGNORECASE | re.UNICODE) for pattern in patterns)


def contains_profanity(text: str) -> bool:
    return _contains_pattern(text, RU_PROFANITY_PATTERNS + EN_PROFANITY_PATTERNS + HE_PROFANITY_PATTERNS)


def noise_signals(text: str) -> list[str]:
    lower = text.casefold()
    words = set(_words(text))
    signals: list[str] = []

    if contains_profanity(text):
        signals.append("profanity_or_aggression")
    if words.intersection(RU_NOISE | EN_NOISE | HE_NOISE):
        signals.append("slang_or_fillers")
    if re.search(r"[!?]{2,}", text):
        signals.append("repeated_punctuation")
    if re.search(r"\b(?:скоклько|сколько\s+время|how much time is it)\b", lower):
        signals.append("grammar_error")
    if text and text[:1].islower():
        signals.append("lowercase_start")
    if len(re.findall(r"[.!?]", text)) >= 3 and len(_words(text)) < 30:
        signals.append("fragmented_short_text")
    return list(dict.fromkeys(signals))


def assess_result(payload: dict, result: dict) -> list[str]:
    """Return reasons that justify one automatic repair pass.

    This deliberately avoids forcing changes to already good text. A retry is
    triggered only when a requested field is missing, the model copied noisy
    input almost verbatim, business mode retained aggression, or short-reply
    mode failed to shorten a long message.
    """
    source = str(payload.get("text") or "").strip()
    mode = str(payload.get("mode") or "business")
    original_requested = bool(payload.get("humanize_original", True))
    translation_requested = bool(payload.get("humanize_translation", True))
    output = str(result.get("humanized_original") or "").strip()
    translation = str(result.get("humanized_translation") or "").strip()
    reasons: list[str] = []

    if original_requested and not output:
        reasons.append("missing_humanized_original")
    if translation_requested and not translation:
        reasons.append("missing_humanized_translation")

    signals = noise_signals(source)
    sim = similarity(source, output) if source and output else 0.0

    preserve_quote = any(
        token in str(payload.get("custom_instruction") or "").casefold()
        for token in ("preserve quote", "keep quote", "сохранить цитату", "не менять цитату", "שמור ציטוט")
    )

    if mode == "business":
        if signals and sim >= 0.84:
            reasons.append("business_rewrite_too_close_to_noisy_input")
        if output and contains_profanity(output) and not preserve_quote:
            reasons.append("business_output_retained_profanity")
        if "slang_or_fillers" in signals:
            out_words = set(_words(output))
            if out_words.intersection(RU_NOISE | EN_NOISE | HE_NOISE):
                reasons.append("business_output_retained_slang")
    elif mode == "friendly":
        if signals and sim >= 0.92:
            reasons.append("friendly_rewrite_too_close_to_noisy_input")
    elif mode == "short_reply":
        source_count = len(_words(source))
        output_count = len(_words(output))
        if source_count >= 18 and output_count > max(14, int(source_count * 0.68)):
            reasons.append("short_reply_not_short_enough")
        if signals and sim >= 0.90:
            reasons.append("short_reply_too_close_to_noisy_input")

    return list(dict.fromkeys(reasons))


def choose_better_result(payload: dict, first: dict, second: dict) -> dict:
    first_reasons = assess_result(payload, first)
    second_reasons = assess_result(payload, second)
    if len(second_reasons) < len(first_reasons):
        return second
    if len(second_reasons) > len(first_reasons):
        return first

    source = str(payload.get("text") or "")
    first_text = str(first.get("humanized_original") or "")
    second_text = str(second.get("humanized_original") or "")
    if similarity(source, second_text) < similarity(source, first_text):
        return second
    return first
