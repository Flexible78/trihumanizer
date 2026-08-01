"""Keyboard layout correction tests.

Runs the Node test suite against static/layout-corrector.js and also checks
the server-side Python mirror in layout_check.py.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from layout_check import validate_layout  # noqa: E402


def test_python_mirror() -> None:
    # ghbdtn rfr ndjb ltkf -> привет как твои дела
    report = validate_layout("ghbdtn rfr ndjb ltkf", "ru")
    assert report["words_changed"] >= 4, report
    assert "привет" in report["corrected"], report["corrected"]
    assert "дела" in report["corrected"], report["corrected"]
    assert report["likely_wrong_layout"] is True

    # руддщ -> hello
    report = validate_layout("руддщ")
    assert report["words_changed"] >= 1
    assert report["corrected"].strip().casefold() == "hello", report["corrected"]

    # correct English stays untouched
    report = validate_layout("hello world this is fine")
    assert report["words_changed"] == 0, report

    # URLs and emails are protected
    report = validate_layout("check https://example.com/ghbdtn and a@b.com")
    assert report["words_changed"] == 0, report

    # Mixed intentional text stays mixed
    report = validate_layout("Напиши email to optical store support")
    assert report["words_changed"] == 0, report

    # Version numbers protected
    report = validate_layout("version 1.6.0 is fine")
    assert report["words_changed"] == 0, report


def test_node_suite() -> None:
    node = "node"
    suite = ROOT / "tests" / "layout_corrector_test.js"
    result = subprocess.run(
        [node, str(suite)],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=str(ROOT),
    )
    if result.returncode != 0:
        raise AssertionError(
            f"layout_corrector_test.js failed:\n{result.stdout}\n{result.stderr}"
        )


if __name__ == "__main__":
    test_python_mirror()
    test_node_suite()
    print("LAYOUT TESTS OK")
