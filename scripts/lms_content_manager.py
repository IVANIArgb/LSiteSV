#!/usr/bin/env python3
"""Ядро LMS Content Manager — создание и управление контентом."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from slugify import slugify

from backend.content_validator import validate_and_fix_structure, maybe_git_commit
from backend.utils.categories_data_sync import (
    get_base_categories_data_path,
    ensure_categories_data_directory,
    get_path_identifier,
)

_FORBIDDEN = re.compile(r'[\\/:*?"<>|]')


def get_content_root() -> str:
    ensure_categories_data_directory()
    return get_base_categories_data_path()


def _root() -> Path:
    return Path(get_content_root())


def _load_json(path: Path) -> dict:
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            d = json.load(f)
            return d if isinstance(d, dict) else {}
    return {}


def _save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _next_ids() -> tuple[int, int, int]:
    base = _root()
    cat_max = course_max = lesson_max = 0
    if not base.exists():
        return 1, 1, 1
    for cat in base.glob("category-*"):
        if not cat.is_dir():
            continue
        c = _load_json(cat / "config.json")
        if isinstance(c.get("id"), int):
            cat_max = max(cat_max, c["id"])
        for course in cat.glob("course-*"):
            if not course.is_dir():
                continue
            cc = _load_json(course / "config.json")
            if isinstance(cc.get("id"), int):
                course_max = max(course_max, cc["id"])
            for lesson in course.glob("lesson-*"):
                if not lesson.is_dir():
                    continue
                lc = _load_json(lesson / "config.json")
                if isinstance(lc.get("id"), int):
                    lesson_max = max(lesson_max, lc["id"])
    return cat_max + 1, course_max + 1, lesson_max + 1


def _find_category_by_title(title: str) -> Optional[Path]:
    title_l = title.strip().lower()
    for cat in _root().glob("category-*"):
        if not cat.is_dir():
            continue
        cfg = _load_json(cat / "config.json")
        if (cfg.get("title") or "").strip().lower() == title_l:
            return cat
    return None


def _find_course_by_title(cat_dir: Path, title: str) -> Optional[Path]:
    title_l = title.strip().lower()
    for course in cat_dir.glob("course-*"):
        if not course.is_dir():
            continue
        cfg = _load_json(course / "config.json")
        if (cfg.get("title") or "").strip().lower() == title_l:
            return course
    return None


def _find_lesson_by_title(course_dir: Path, title: str) -> Optional[Path]:
    title_l = title.strip().lower()
    for lesson in course_dir.glob("lesson-*"):
        if not lesson.is_dir():
            continue
        cfg = _load_json(lesson / "config.json")
        if (cfg.get("title") or "").strip().lower() == title_l:
            return lesson
    return None


def _validate_title(title: str) -> bool:
    return bool(title.strip()) and not _FORBIDDEN.search(title)


def cmd_create_category(title: str) -> None:
    if not _validate_title(title):
        print("Некорректное название категории.")
        return
    cat_id, _, _ = _next_ids()
    slug = slugify(title, max_length=50)
    cat_dir = _root() / f"category-{slug}"
    if cat_dir.exists():
        print(f"Категория уже существует: {cat_dir}")
        return
    cat_dir.mkdir(parents=True)
    cfg = {
        "id": cat_id,
        "title": title.strip(),
        "path_identifier": get_path_identifier(title.strip()),
        "type": "category",
        "order": cat_id,
        "is_active": True,
        "sequential_progression": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _save_json(cat_dir / "config.json", cfg)
    print(f"Создана категория: {cat_dir}")
    maybe_git_commit(f"LMS: create category {title}")


def cmd_create_course(category_title: str, course_title: str, description: str = "") -> None:
    cat_dir = _find_category_by_title(category_title)
    if not cat_dir:
        print(f"Категория «{category_title}» не найдена.")
        return
    if not _validate_title(course_title):
        print("Некорректное название курса.")
        return
    _, course_id, _ = _next_ids()
    slug = slugify(course_title, max_length=50)
    course_dir = cat_dir / f"course-{slug}"
    if course_dir.exists():
        print("Курс уже существует.")
        return
    course_dir.mkdir(parents=True)
    cat_cfg = _load_json(cat_dir / "config.json")
    cfg = {
        "id": course_id,
        "title": course_title.strip(),
        "category_id": cat_cfg.get("id"),
        "description": description,
        "order": 1,
        "total_lessons": 0,
        "is_active": True,
        "sequential_progression": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _save_json(course_dir / "config.json", cfg)
    print(f"Создан курс: {course_dir}")
    maybe_git_commit(f"LMS: create course {course_title}")


def cmd_create_lesson(category_title: str, course_title: str, lesson_title: str) -> None:
    cat_dir = _find_category_by_title(category_title)
    if not cat_dir:
        print(f"Категория «{category_title}» не найдена.")
        return
    course_dir = _find_course_by_title(cat_dir, course_title)
    if not course_dir:
        print(f"Курс «{course_title}» не найден.")
        return
    if not _validate_title(lesson_title):
        print("Некорректное название урока.")
        return
    _, _, lesson_id = _next_ids()
    slug = slugify(lesson_title, max_length=50)
    lesson_dir = course_dir / f"lesson-{slug}"
    if lesson_dir.exists():
        print("Урок уже существует.")
        return
    for sub in ("texts", "images", "videos", "files", "tests"):
        (lesson_dir / sub).mkdir(parents=True)
    num = len(list(course_dir.glob("lesson-*"))) + 1
    course_cfg = _load_json(course_dir / "config.json")
    cfg = {
        "id": lesson_id,
        "title": lesson_title.strip(),
        "course_id": course_cfg.get("id"),
        "lesson_number": num,
        "order": num,
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _save_json(lesson_dir / "config.json", cfg)
    (lesson_dir / "texts" / "block-1.txt").write_text(f"# {lesson_title}\n\nТекст урока...", encoding="utf-8")
    _save_json(lesson_dir / "blocks.json", {
        "blocks": [{"id": 1, "block_type": "heading", "order": 1, "content": {"text": ""}}]
    })
    course_cfg["total_lessons"] = num
    _save_json(course_dir / "config.json", course_cfg)
    print(f"Создан урок: {lesson_dir}")
    maybe_git_commit(f"LMS: create lesson {lesson_title}")


def cmd_create_test(category_title: str, course_title: str, lesson_title: str, test_title: str = "Тест") -> None:
    cat_dir = _find_category_by_title(category_title)
    if not cat_dir:
        return
    course_dir = _find_course_by_title(cat_dir, course_title)
    if not course_dir:
        return
    lesson_dir = _find_lesson_by_title(course_dir, lesson_title)
    if not lesson_dir:
        return
    blocks_data = _load_json(lesson_dir / "blocks.json")
    blocks = list(blocks_data.get("blocks") or [])
    new_id = max((b.get("id") or 0 for b in blocks), default=0) + 1
    order = max((b.get("order") or 0 for b in blocks), default=0) + 1
    blocks.append({"id": new_id, "block_type": "test", "order": order, "content": {"title": test_title}})
    _save_json(lesson_dir / "blocks.json", {"blocks": blocks})
    test_dir = lesson_dir / "tests" / f"block-{new_id}"
    test_dir.mkdir(parents=True)
    (test_dir / "questions").mkdir(exist_ok=True)
    _save_json(test_dir / "config.json", {
        "title": test_title,
        "enabled": True,
        "pass_percent": 70,
        "limit_attempts": False,
        "max_attempts": None,
        "test_type": "permanent",
        "shuffle_questions": False,
        "shuffle_options": False,
        "time_limit_seconds": None,
    })
    (test_dir / "questions" / "q001.txt").write_text(
        f"Q: {test_title}\nA) Да\nB) Нет\nPOINTS: 1\nTYPE: single\nCORRECT: A\n",
        encoding="utf-8",
    )
    print(f"Тест block-{new_id} создан.")
    maybe_git_commit("LMS: create test")


def cmd_show_tree() -> None:
    base = _root()
    print(f"\nКорень контента: {base}\n")
    for cat_dir in sorted(base.glob("category-*")):
        if not cat_dir.is_dir():
            continue
        cat_cfg = _load_json(cat_dir / "config.json")
        print(f"📁 {cat_cfg.get('title', cat_dir.name)}")
        for course_dir in sorted(cat_dir.glob("course-*")):
            if not course_dir.is_dir():
                continue
            course_cfg = _load_json(course_dir / "config.json")
            print(f"  📂 {course_cfg.get('title', course_dir.name)}")
            for lesson_dir in sorted(course_dir.glob("lesson-*")):
                if not lesson_dir.is_dir():
                    continue
                lesson_cfg = _load_json(lesson_dir / "config.json")
                blocks = _load_json(lesson_dir / "blocks.json").get("blocks") or []
                tests = sum(1 for b in blocks if b.get("block_type") == "test")
                print(f"    📝 {lesson_cfg.get('title', lesson_dir.name)} ({len(blocks)} блоков, {tests} тестов)")


def cmd_validate() -> None:
    report = validate_and_fix_structure(fix=True)
    print(
        f"Проверено: кат={report.categories_checked} кур={report.courses_checked} "
        f"ур={report.lessons_checked}, исправлено={report.fixed_count}"
    )


def cmd_export_course(category_title: str, course_title: str) -> None:
    cat_dir = _find_category_by_title(category_title)
    if not cat_dir:
        print("Категория не найдена.")
        return
    course_dir = _find_course_by_title(cat_dir, course_title)
    if not course_dir:
        print("Курс не найден.")
        return
    out_dir = PROJECT_ROOT / "backups" / "exports"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_path = out_dir / f"course_{course_dir.name}_{ts}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for fp in course_dir.rglob("*"):
            if fp.is_file():
                zf.write(fp, fp.relative_to(cat_dir.parent))
    print(f"Экспорт: {zip_path}")


def cmd_import_course(zip_path: str, category_title: str) -> None:
    cat_dir = _find_category_by_title(category_title)
    if not cat_dir:
        print("Категория не найдена.")
        return
    zp = Path(zip_path)
    if not zp.exists():
        print("ZIP не найден.")
        return
    with zipfile.ZipFile(zp, "r") as zf:
        names = zf.namelist()
        roots = {n.split("/")[0] for n in names if n and not n.endswith("/")}
        course_roots = {r for r in roots if r.startswith("course-")} or roots
        for root_name in course_roots:
            dest = cat_dir / root_name
            if dest.exists():
                shutil.rmtree(dest)
            dest.mkdir(parents=True)
            prefix = root_name + "/"
            for name in names:
                if name.startswith(prefix) and not name.endswith("/"):
                    rel = name[len(prefix):]
                    target = dest / rel
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(name) as src, open(target, "wb") as out:
                        out.write(src.read())
    validate_and_fix_structure(fix=True)
    print("Импорт завершён.")
    maybe_git_commit("LMS: import course")


def cmd_set_content_root(new_path: str) -> None:
    new_path = os.path.abspath(os.path.expanduser(new_path.strip().strip('"')))
    os.makedirs(new_path, exist_ok=True)
    env_path = PROJECT_ROOT / ".env"
    lines = env_path.read_text(encoding="utf-8").splitlines(keepends=True) if env_path.exists() else []
    key = "CONTENT_ROOT_DIR"
    out, found = [], False
    for line in lines:
        if line.strip().startswith(f"{key}="):
            out.append(f"{key}={new_path}\n")
            found = True
        else:
            out.append(line if line.endswith("\n") else line + "\n")
    if not found:
        out.append(f"{key}={new_path}\n")
    env_path.write_text("".join(out), encoding="utf-8")
    (PROJECT_ROOT / ".content_root_dir_override").write_text(new_path, encoding="utf-8")
    os.environ["CONTENT_ROOT_DIR"] = new_path
    print(f"CONTENT_ROOT_DIR = {new_path}")


def _cli_main(argv: list[str]) -> int:
    if not argv:
        return 1
    cmd = argv[0]
    rest = argv[1:]

    if cmd == "create-category":
        title = " ".join(rest) if rest else input("Название категории: ").strip()
        if not title:
            return 1
        cmd_create_category(title)
        return 0
    if cmd == "create-course":
        if len(rest) >= 2:
            cmd_create_course(rest[0], rest[1])
        else:
            cmd_create_course(input("Категория: "), input("Курс: "))
        return 0
    if cmd == "create-lesson":
        if len(rest) >= 3:
            cmd_create_lesson(rest[0], rest[1], rest[2])
        else:
            cmd_create_lesson(input("Категория: "), input("Курс: "), input("Урок: "))
        return 0
    if cmd == "create-test":
        if len(rest) >= 3:
            title = rest[3] if len(rest) > 3 else "Тест"
            cmd_create_test(rest[0], rest[1], rest[2], title)
        return 0
    if cmd == "tree":
        cmd_show_tree()
        return 0
    if cmd == "validate":
        cmd_validate()
        return 0
    if cmd == "set-root":
        if rest:
            cmd_set_content_root(rest[0])
        return 0
    if cmd == "menu":
        cmd_show_tree()
        return 0
    print(f"Неизвестная команда: {cmd}")
    return 1


def main() -> int:
    return _cli_main(sys.argv[1:])


if __name__ == "__main__":
    sys.exit(main())
