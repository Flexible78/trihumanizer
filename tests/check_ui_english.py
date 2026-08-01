"""Check that the public UI contains no unintended Russian-language copy.

Cyrillic characters are allowed only in:
- language processing code and dictionaries (layout-corrector.js, layout_check.py)
- test fixtures
- user-visible language names that are themselves in the target language
  (e.g. the Hebrew option label "עברית")
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Files that legitimately contain Cyrillic/Hebrew data or fixtures.
ALLOWED_CYRILLIC = {
    "static/layout-corrector.js",
    "static/speech.js",
    "layout_check.py",
    "quality.py",
    "prompts.py",
    "tests/layout_corrector_test.js",
    "tests/test_layout.py",
    "tests/self_test.py",
    "tests/test_intent.py",
    "pdf_export.py",
    "README.md",
    "CHANGELOG.md",
    "QUALITY_ALGORITHM.md",
    "BROWSER_VOICE.md",
    "VALIDATION.md",
}

# Allowed Russian words inside UI-adjacent files (mostly "ru" language tags).
ALLOWED_TOKENS = {"ru", "rus", "russian", "ru-ru"}

UI_FILES = [
    "templates/index.html",
    "static/app.js",
    "static/speech.js",
    "static/styles.css",
    "static/sw.js",
]

# static/speech.js uses a Cyrillic regex to auto-detect the spoken language;
# that is language-processing code, allowed by the English-only policy. The
# tokens below are the fragments of the detection regex itself.
ALLOWED_CYRILLIC_JS = {
    "static/speech.js": ["А", "Яа", "яЁё"],
}


def find_cyrillic(text: str) -> set[str]:
    words = re.findall(r"[А-Яа-яЁё]+", text)
    return {word for word in words if word.lower() not in ALLOWED_TOKENS}


def check_ui() -> list[str]:
    problems: list[str] = []
    for name in UI_FILES:
        path = ROOT / name
        if not path.exists():
            problems.append(f"missing UI file: {name}")
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        found = find_cyrillic(text)
        allowed = set(ALLOWED_CYRILLIC_JS.get(name, []))
        unexpected = {word for word in found if word not in allowed}
        if unexpected:
            problems.append(f"{name}: unexpected Russian words: {sorted(unexpected)[:20]}")
    return problems


def check_allowed_files() -> list[str]:
    """Ensure files with Cyrillic are intentional (tests/fixtures only)."""
    problems: list[str] = []
    for path in sorted((ROOT / "static").glob("*.js")):
        rel = f"static/{path.name}"
        text = path.read_text(encoding="utf-8", errors="replace")
        if re.search(r"[А-Яа-яЁё]", text) and rel not in ALLOWED_CYRILLIC:
            problems.append(f"{rel}: contains Cyrillic but is not in the allowed list")
    return problems


def main() -> int:
    problems = check_ui() + check_allowed_files()
    if problems:
        for problem in problems:
            print(f"FAIL: {problem}")
        return 1
    print("UI ENGLISH CHECK OK — no unintended Russian copy in public UI")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
