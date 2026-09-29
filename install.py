#!/usr/bin/env python3
"""
Установщик LearningSite для Windows, Linux и macOS.

Запуск:
  Windows:  Установить.bat
  Linux/macOS:  ./install.sh
  или:  python3 install.py
"""
from __future__ import annotations

import os
import platform
import secrets
import shutil
import subprocess
import sys
import time
from pathlib import Path

SOURCE = Path(__file__).resolve().parent
SKIP_NAMES = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".cursor",
    "node_modules",
    ".idea",
    ".vscode",
    "backups",
}


def configure_stdout() -> None:
    if os.name == "nt":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass


def ask_yes_no(prompt: str, default: bool = True) -> bool:
    hint = "Д/н" if default else "д/Н"
    while True:
        raw = input(f"{prompt} [{hint}]: ").strip().lower()
        if not raw:
            return default
        if raw in ("д", "да", "y", "yes"):
            return True
        if raw in ("н", "нет", "n", "no"):
            return False
        print("Введите «да» или «нет».")


def print_terms() -> None:
    terms = SOURCE / "TERMS.txt"
    print("\n" + "=" * 64)
    print("УСЛОВИЯ ИСПОЛЬЗОВАНИЯ")
    print("=" * 64)
    if terms.exists():
        print(terms.read_text(encoding="utf-8"))
    else:
        print("Учебный проект LearningSite. Согласие нужно для установки Python и библиотек.")
    print("=" * 64 + "\n")


def desktop_dir() -> Path:
    home = Path.home()
    if os.name == "nt":
        return home / "Desktop"
    linux = home / "Desktop"
    if linux.exists():
        return linux
    xdg = home / "Рабочий стол"
    if xdg.exists():
        return xdg
    return linux


def python_candidates() -> list[Path]:
    found: list[Path] = []
    for name in ("python3", "python", "py"):
        p = shutil.which(name)
        if p:
            found.append(Path(p))
    if os.name == "nt":
        local = Path.home() / "AppData" / "Local" / "Programs" / "Python"
        if local.exists():
            for exe in sorted(local.glob("Python3*/python.exe"), reverse=True):
                found.append(exe)
        pf = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Python312" / "python.exe"
        if pf.exists():
            found.append(pf)
    return found


def python_ok(exe: Path) -> bool:
    try:
        out = subprocess.check_output(
            [str(exe), "-c", "import sys; print(sys.version_info.major, sys.version_info.minor)"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
        parts = out.split()
        major, minor = int(parts[0]), int(parts[1])
        return major == 3 and minor >= 9
    except Exception:
        return False


def find_usable_python() -> Path | None:
    seen = set()
    for cand in python_candidates():
        key = str(cand.resolve()) if cand.exists() else str(cand)
        if key in seen:
            continue
        seen.add(key)
        if cand.name.lower() == "py.exe" or cand.name.lower() == "py":
            try:
                subprocess.check_output([str(cand), "-3", "-c", "pass"], stderr=subprocess.DEVNULL)
                return cand
            except Exception:
                continue
        if python_ok(cand):
            return cand
    return None


def py_cmd(exe: Path) -> list[str]:
    if exe.name.lower() in ("py", "py.exe"):
        return [str(exe), "-3"]
    return [str(exe)]


def install_python_windows() -> bool:
    winget = shutil.which("winget")
    if winget:
        print("Устанавливаю Python через winget…")
        code = subprocess.call(
            [
                winget,
                "install",
                "-e",
                "--id",
                "Python.Python.3.12",
                "--accept-package-agreements",
                "--accept-source-agreements",
            ]
        )
        return code == 0
    print("winget не найден. Установите Python 3.12+ с python.org и запустите установщик снова.")
    return False


def install_python_unix() -> bool:
    system = platform.system().lower()
    if system == "darwin":
        brew = shutil.which("brew")
        if not brew:
            print("Установите Homebrew или Python 3.12+ вручную: https://www.python.org/downloads/")
            return False
        print("Устанавливаю Python через Homebrew…")
        return subprocess.call([brew, "install", "python@3.12"]) == 0
    if shutil.which("apt-get"):
        print("Устанавливаю Python через apt (нужны права администратора)…")
        return (
            subprocess.call(["sudo", "apt-get", "update"]) == 0
            and subprocess.call(
                ["sudo", "apt-get", "install", "-y", "python3", "python3-venv", "python3-pip"]
            )
            == 0
        )
    if shutil.which("dnf"):
        print("Устанавливаю Python через dnf…")
        return subprocess.call(["sudo", "dnf", "install", "-y", "python3", "python3-pip", "python3-virtualenv"]) == 0
    if shutil.which("pacman"):
        print("Устанавливаю Python через pacman…")
        return subprocess.call(["sudo", "pacman", "-Sy", "--noconfirm", "python", "python-pip"]) == 0
    print("Не удалось автоматически поставить Python. Установите python3 (>=3.9) вручную.")
    return False


def ensure_python() -> Path:
    exe = find_usable_python()
    if exe:
        print(f"Найден Python: {exe}")
        return exe
    print("Python 3.9+ не найден.")
    if os.name == "nt":
        ok = install_python_windows()
    else:
        ok = install_python_unix()
    if not ok:
        raise SystemExit(1)
    time.sleep(2)
    exe = find_usable_python()
    if not exe:
        print("Python установлен, но не виден в PATH. Закройте окно и запустите установщик ещё раз.")
        raise SystemExit(1)
    return exe


def copy_project(dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    if dest.resolve() == SOURCE.resolve():
        print("Установка в текущую папку — копирование не требуется.")
        return
    print(f"Копирую проект в {dest} …")

    def ignore(directory: str, names: list[str]) -> set[str]:
        skipped = set()
        for n in names:
            if n in SKIP_NAMES or n.endswith(".pyc"):
                skipped.add(n)
        return skipped

    for item in SOURCE.iterdir():
        if item.name in SKIP_NAMES or item.name == ".env":
            continue
        target = dest / item.name
        if item.is_dir():
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(item, target, ignore=ignore)
        else:
            shutil.copy2(item, target)


def venv_python(root: Path) -> Path:
    if os.name == "nt":
        return root / ".venv" / "Scripts" / "python.exe"
    return root / ".venv" / "bin" / "python"


def write_env(root: Path) -> None:
    env_path = root / ".env"
    if env_path.exists():
        print(".env уже есть — не перезаписываю.")
        return
    key = secrets.token_urlsafe(32)
    env_path.write_text(
        "\n".join(
            [
                "FLASK_ENV=development",
                "DEBUG=true",
                f"SECRET_KEY={key}",
                "INSECURE_DEV_SECRET=true",
                "HOST=127.0.0.1",
                "PORT=5000",
                "RUN_WITH_GUNICORN=false",
                "TEST_MODE=true",
                "TEST_MODE_AUTH_BYPASS=true",
                "TEST_MODE_DEFAULT_USER=testadmin",
                "TEST_MODE_DEFAULT_FULL_NAME=Демо администратор",
                "KERBEROS_AUTH_ENABLED=false",
                "LDAP_ENABLED=false",
                "DB_SEED_ON_START=true",
                "CONTENT_ROOT_DIR=",
                "TERMINAL_ROLE_COMMANDS_ENABLED=true",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print("Создан файл .env для учебного режима.")


def write_desktop_launchers(root: Path) -> None:
    desk = desktop_dir()
    desk.mkdir(parents=True, exist_ok=True)
    py = venv_python(root)
    start_py = root / "start" / "start_server.py"
    stop_py = root / "start" / "stop_server.py"
    if os.name == "nt":
        start = desk / "LearningSite-запуск.bat"
        stop = desk / "LearningSite-остановка.bat"
        start.write_text(
            f'@echo off\r\nchcp 65001 >nul\r\n"{py}" "{start_py}"\r\npause\r\n',
            encoding="utf-8",
        )
        stop.write_text(
            f'@echo off\r\nchcp 65001 >nul\r\n"{py}" "{stop_py}"\r\npause\r\n',
            encoding="utf-8",
        )
    else:
        start = desk / "LearningSite-запуск.sh"
        stop = desk / "LearningSite-остановка.sh"
        start.write_text(f"#!/bin/sh\nexec '{py}' '{start_py}'\n", encoding="utf-8")
        stop.write_text(f"#!/bin/sh\nexec '{py}' '{stop_py}'\n", encoding="utf-8")
        start.chmod(0o755)
        stop.chmod(0o755)
    print(f"Ярлыки созданы на рабочем столе:\n  {start}\n  {stop}")


def run_pip(py: Path, root: Path) -> None:
    subprocess.check_call(py_cmd(py) + ["-m", "venv", str(root / ".venv")], cwd=str(root))
    vpy = venv_python(root)
    subprocess.check_call([str(vpy), "-m", "pip", "install", "--upgrade", "pip"], cwd=str(root))
    subprocess.check_call(
        [str(vpy), "-m", "pip", "install", "-r", str(root / "requirements.txt")],
        cwd=str(root),
    )


def main() -> int:
    configure_stdout()
    print("\nLearningSite — установка учебного портала\n")
    print_terms()
    if not ask_yes_no(
        "Согласны с условиями и с установкой Python, pip и библиотек проекта?",
        True,
    ):
        print("Установка отменена.")
        return 0

    default_dest = desktop_dir() / "LearningSite"
    if (SOURCE / "run.py").exists():
        default_dest = SOURCE
    raw = input(f"Куда установить проект? [{default_dest}]: ").strip()
    dest = Path(raw).expanduser() if raw else default_dest
    dest = dest.resolve()
    copy_project(dest)

    os.chdir(dest)
    py = ensure_python()
    print("Создаю виртуальное окружение и ставлю библиотеки…")
    run_pip(py, dest)
    write_env(dest)
    (dest / "runtime").mkdir(exist_ok=True)
    print("\nУстановка завершена.")
    print(f"Папка проекта: {dest}")
    print("Сайт после запуска: http://127.0.0.1:5000")

    if ask_yes_no("Создать на рабочем столе файлы запуска и остановки сервера?", True):
        write_desktop_launchers(dest)

    if ask_yes_no("Запустить сервер сейчас?", True):
        vpy = venv_python(dest)
        print("Запускаю сервер. Окно можно не закрывать. Остановка — файл на рабочем столе или Ctrl+C.")
        os.chdir(dest)
        return subprocess.call([str(vpy), str(dest / "run.py")])
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nПрервано.")
        raise SystemExit(130)
