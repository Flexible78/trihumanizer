from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
APP_PID_FILE = DATA_DIR / "app.pid"
LAUNCHER_PID_FILE = DATA_DIR / "launcher.pid"
PORT_FILE = DATA_DIR / "app.port"
LOG_FILE = DATA_DIR / "server.log"
LAUNCHER_LOG = DATA_DIR / "launcher.log"
RESTART_EXIT_CODE = 75


def log(message: str) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    with LAUNCHER_LOG.open("a", encoding="utf-8") as handle:
        handle.write(f"[{stamp}] {message}\n")


def health_ok(port: int, timeout: float = 1.5) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=timeout) as response:
            return response.status == 200
    except Exception:
        return False


def existing_port() -> int | None:
    if not PORT_FILE.exists():
        return None
    try:
        port = int(PORT_FILE.read_text(encoding="ascii").strip())
    except (ValueError, OSError):
        return None
    return port if health_ok(port) else None


def free_port(start: int = 8868, attempts: int = 60) -> int:
    for port in range(start, start + attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError("No free local port was found.")


def wait_for_health(port: int, timeout: float = 30.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if health_ok(port):
            return True
        time.sleep(0.3)
    return False


def start_child(port: int) -> subprocess.Popen:
    env = os.environ.copy()
    env["TRIHUMANIZER_PORT"] = str(port)
    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
    log_handle = LOG_FILE.open("a", encoding="utf-8")
    process = subprocess.Popen(
        [sys.executable, "app.py"],
        cwd=BASE_DIR,
        env=env,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        creationflags=creationflags,
    )
    process._trihumanizer_log_handle = log_handle  # type: ignore[attr-defined]
    APP_PID_FILE.write_text(str(process.pid), encoding="ascii")
    return process


def close_child_log(process: subprocess.Popen) -> None:
    handle = getattr(process, "_trihumanizer_log_handle", None)
    if handle:
        handle.close()


def main() -> int:
    DATA_DIR.mkdir(exist_ok=True)
    LAUNCHER_PID_FILE.write_text(str(os.getpid()), encoding="ascii")

    current = existing_port()
    if current:
        log(f"Existing application detected on port {current}; opening browser only.")
        webbrowser.open(f"http://127.0.0.1:{current}")
        LAUNCHER_PID_FILE.unlink(missing_ok=True)
        return 0

    port = free_port()
    PORT_FILE.write_text(str(port), encoding="ascii")
    browser_opened = False

    try:
        while True:
            process = start_child(port)
            log(f"Application process started: pid={process.pid}, port={port}.")
            if not wait_for_health(port):
                log("Application did not become healthy. See server.log.")
                process.terminate()
                close_child_log(process)
                return 1

            if not browser_opened:
                webbrowser.open(f"http://127.0.0.1:{port}")
                browser_opened = True

            code = process.wait()
            close_child_log(process)
            APP_PID_FILE.unlink(missing_ok=True)
            log(f"Application process exited with code {code}.")

            if code == RESTART_EXIT_CODE:
                log("Restart requested from the browser.")
                time.sleep(0.45)
                continue
            return 0 if code == 0 else code
    except Exception as exc:
        log(f"Launcher error: {exc!r}")
        return 1
    finally:
        APP_PID_FILE.unlink(missing_ok=True)
        LAUNCHER_PID_FILE.unlink(missing_ok=True)
        PORT_FILE.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
