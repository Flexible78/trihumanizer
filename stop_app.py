from __future__ import annotations

import os
import signal
import subprocess
from pathlib import Path

base = Path(__file__).resolve().parent
data = base / "data"
files = [data / "app.pid", data / "launcher.pid"]

pids: list[int] = []
for file in files:
    if not file.exists():
        continue
    try:
        value = int(file.read_text(encoding="ascii").strip())
        if value not in pids:
            pids.append(value)
    except (ValueError, OSError):
        pass

if not pids:
    print("TriHumanizer Translator is already stopped.")
    raise SystemExit(0)

for pid in pids:
    try:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        pass

for file in files + [data / "app.port"]:
    file.unlink(missing_ok=True)

print("TriHumanizer Translator stopped.")
