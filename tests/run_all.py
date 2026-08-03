"""Run the complete TriHumanizer test suite.

Usage:
    python tests/run_all.py
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# A non-secret dummy key so "configured" flags are testable and provider
# resolution never depends on the developer's real environment.
os.environ.setdefault("MISTRAL_API_KEY", "test-dummy-key-not-a-secret")

FAILURES: list[str] = []


def run_module(name: str, env_extra: dict[str, str] | None = None) -> None:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    if env_extra:
        env.update(env_extra)
    result = subprocess.run(
        [sys.executable, str(ROOT / "tests" / name)],
        capture_output=True,
        text=True,
        timeout=300,
        cwd=str(ROOT),
        env=env,
    )
    if result.returncode != 0:
        FAILURES.append(name)
        print(f"FAIL: {name}\n{result.stdout}{result.stderr}")
    else:
        print(f"ok: {name}")


def run_node(name: str) -> None:
    result = subprocess.run(
        ["node", str(ROOT / "tests" / name)],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=str(ROOT),
    )
    if result.returncode != 0:
        FAILURES.append(name)
        print(f"FAIL: {name}\n{result.stdout}{result.stderr}")
    else:
        print(f"ok: {name}")


def run_ui_check() -> None:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    result = subprocess.run(
        [sys.executable, str(ROOT / "tests" / "check_ui_english.py")],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=str(ROOT),
        env=env,
    )
    if result.returncode != 0:
        FAILURES.append("check_ui_english.py")
        print(f"FAIL: check_ui_english.py\n{result.stdout}{result.stderr}")
    else:
        print("ok: check_ui_english.py")


def main() -> int:
    print("TriHumanizer test suite — 1.7.0")
    print("=" * 50)

    run_module("self_test.py")
    run_module("test_intent.py")
    run_module("test_layout.py")
    run_module("test_security.py")
    run_module("test_deployment.py")
    run_ui_check()
    run_node("shortcuts_test.js")
    run_node("layout_corrector_test.js")

    print("=" * 50)
    if FAILURES:
        print(f"FAILED: {len(FAILURES)} module(s): {', '.join(FAILURES)}")
        return 1
    print("ALL TESTS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
