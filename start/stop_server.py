#!/usr/bin/env python3
"""Остановка учебного сервера LearningSite."""
from __future__ import annotations

import os
import signal
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PID_FILE = ROOT / "runtime" / "server.pid"


def main() -> int:
    if not PID_FILE.exists():
        print("Сервер не найден (нет runtime/server.pid).")
        return 0
    try:
        pid = int(PID_FILE.read_text(encoding="utf-8").strip())
    except ValueError:
        PID_FILE.unlink(missing_ok=True)
        print("Повреждённый PID-файл удалён.")
        return 0
    try:
        if os.name == "nt":
            os.kill(pid, signal.SIGTERM)
        else:
            os.kill(pid, signal.SIGTERM)
        time.sleep(0.6)
    except OSError as exc:
        print(f"Процесс {pid} уже не работает: {exc}")
    PID_FILE.unlink(missing_ok=True)
    print("Сервер остановлен.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
