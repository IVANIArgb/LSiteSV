#!/usr/bin/env python3
"""Запуск учебного сервера LearningSite. Пишет PID в runtime/server.pid."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNTIME = ROOT / "runtime"
PID_FILE = RUNTIME / "server.pid"
LOG_FILE = RUNTIME / "server.log"


def venv_python() -> Path:
    if os.name == "nt":
        return ROOT / ".venv" / "Scripts" / "python.exe"
    return ROOT / ".venv" / "bin" / "python"


def main() -> int:
    py = venv_python()
    if not py.exists():
        print("Не найдено виртуальное окружение. Сначала запустите install.py")
        return 1
    RUNTIME.mkdir(parents=True, exist_ok=True)
    if PID_FILE.exists():
        print(f"Похоже, сервер уже запущен (файл {PID_FILE}).")
        print("Сначала выполните start/stop_server.py")
        return 0
    log = open(LOG_FILE, "a", encoding="utf-8")
    kwargs = {
        "cwd": str(ROOT),
        "stdout": log,
        "stderr": subprocess.STDOUT,
    }
    if os.name == "nt":
        kwargs["creationflags"] = (
            subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
        )
    else:
        kwargs["start_new_session"] = True
    proc = subprocess.Popen([str(py), str(ROOT / "run.py")], **kwargs)
    PID_FILE.write_text(str(proc.pid), encoding="utf-8")
    print("Сервер LearningSite запущен.")
    print("Откройте в браузере: http://127.0.0.1:5000")
    print(f"PID: {proc.pid}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
