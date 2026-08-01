"""Optional live research adapter.

Provider-independent: it uses the OpenAI-compatible chat API configured via
environment variables:

- RESEARCH_ENABLED      (1/true/on)
- RESEARCH_PROVIDER     provider id from the catalog, or "custom"
- RESEARCH_MODEL        model name
- RESEARCH_API_KEY      API key (server-side only)
- RESEARCH_BASE_URL     optional OpenAI-compatible base URL

When disabled, callers must not hallucinate facts: they should ask the user
for the relevant URL/information and keep generating with available facts.
"""
from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from typing import Any

from llm_client import LLMError, chat_completion, redact_secrets

DEFAULT_RESEARCH_SYSTEM = """You are a careful web research assistant.
You answer ONLY from information the user or the conversation supplies.
If you cannot verify current facts (prices, opening hours, stock, policies),
say so explicitly and never invent them.
Return JSON only:
{
  "answer": "concise answer to the user's question",
  "verified_findings": ["fact 1", "fact 2"],
  "sources": [{"title": "source title", "url": "https://..."}],
  "needs_user_input": ["opening hours", "stock status"],
  "notes": "anything the user should verify manually"
}"""


def research_enabled() -> bool:
    return os.environ.get("RESEARCH_ENABLED", "").strip().lower() in {"1", "true", "yes", "on"}


def _research_provider() -> str:
    provider = os.environ.get("RESEARCH_PROVIDER", "").strip().lower()
    return provider or "custom"


def _research_model() -> str:
    return os.environ.get("RESEARCH_MODEL", "").strip() or ""


def _research_key() -> str:
    return os.environ.get("RESEARCH_API_KEY", "").strip()


def _research_base_url() -> str:
    return os.environ.get("RESEARCH_BASE_URL", "").strip()


def run_research(
    query: str,
    *,
    provider: str = "",
    model: str = "",
    api_key: str = "",
    base_url: str = "",
    timeout: int = 60,
) -> dict[str, Any]:
    """Run a research request against the configured research provider.

    Returns a dict with answer/findings/sources or raises LLMError. The caller
    decides how to degrade when research is unavailable.
    """
    provider = provider or _research_provider()
    model = model or _research_model()
    api_key = api_key or _research_key()
    base_url = base_url or _research_base_url()

    if not model:
        raise LLMError("Research is enabled but RESEARCH_MODEL is not configured.")

    messages = [
        {"role": "system", "content": DEFAULT_RESEARCH_SYSTEM},
        {"role": "user", "content": f"<RESEARCH_QUERY>\n{query[:4000]}\n</RESEARCH_QUERY>"},
    ]
    result, endpoint = chat_completion(
        provider=provider,
        model=model,
        api_key=api_key,
        custom_url=base_url,
        messages=messages,
        temperature=0.0,
        timeout=timeout,
    )
    content = str(
        result.get("answer")
        or result.get("humanized_translation")
        or result.get("cleaned_request")
        or ""
    ).strip()
    return parse_research_output(content)


def parse_research_output(content: str) -> dict[str, Any]:
    """Parse the research JSON tolerantly; never crash on malformed output."""
    raw = content.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
    raw = re.sub(r"\s*```$", "", raw)
    first = raw.find("{")
    last = raw.rfind("}")
    if first >= 0 and last > first:
        raw = raw[first : last + 1]
    value: dict[str, Any] = {}
    import json

    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            value = parsed
    except json.JSONDecodeError:
        value = {"answer": content, "notes": "Research returned non-JSON output."}

    sources = value.get("sources") or []
    if not isinstance(sources, list):
        sources = [sources] if isinstance(sources, dict) else []
    clean_sources = []
    for source in sources:
        if isinstance(source, dict):
            clean_sources.append(
                {
                    "title": str(source.get("title") or "Source").strip()[:200],
                    "url": str(source.get("url") or "").strip()[:500],
                }
            )
        elif isinstance(source, str) and source.strip():
            clean_sources.append({"title": source.strip()[:200], "url": ""})

    findings = value.get("verified_findings") or []
    if not isinstance(findings, list):
        findings = [str(findings)] if findings else []
    findings = [redact_secrets(str(item).strip())[:1000] for item in findings if str(item).strip()]

    needs_input = value.get("needs_user_input") or []
    if not isinstance(needs_input, list):
        needs_input = [str(needs_input)] if needs_input else []

    return {
        "answer": redact_secrets(str(value.get("answer") or "").strip())[:6000],
        "verified_findings": findings,
        "sources": clean_sources[:10],
        "needs_user_input": [str(item)[:200] for item in needs_input[:8]],
        "notes": redact_secrets(str(value.get("notes") or "").strip())[:1000],
        "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
