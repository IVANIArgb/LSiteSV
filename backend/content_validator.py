"""
Валидация и автогенерация структуры контента LMS.
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from backend.utils.categories_data_sync import (
    ensure_categories_data_directory,
    get_base_categories_data_path,
)
from backend.utils.lesson_blocks_fs import read_blocks, write_blocks
from backend.utils.test_fs import FsTestConfig, write_test_config

logger = logging.getLogger(__name__)

_content_cache_version: int = 0
_cache_lock = threading.Lock()

_FORBIDDEN_NAME_CHARS = re.compile(r'[\\/:*?"<>|]')
_RE_IMAGE = re.compile(r"\[IMAGE:\s*([^\]]+)\]", re.IGNORECASE)
_RE_VIDEO = re.compile(r"\[VIDEO:\s*([^\]]+)\]", re.IGNORECASE)
_RE_FILE = re.compile(r"\[FILE:\s*([^\]]+)\]", re.IGNORECASE)
_TEST_START = "=== ТЕСТ НАЧАЛО ==="
_TEST_END = "=== ТЕСТ КОНЕЦ ==="

DEFAULT_CATEGORY_CONFIG = {"order": 1, "is_active": True, "sequential_progression": False}
DEFAULT_COURSE_CONFIG = {
    "description": "",
    "order": 1,
    "total_lessons": 0,
    "is_active": True,
    "sequential_progression": True,
}
DEFAULT_LESSON_CONFIG = {"lesson_number": 1, "order": 1, "is_active": True}


@dataclass
class ValidationIssue:
    path: str
    issue: str
    fixed: bool = False
    action: str = ""


@dataclass
class ValidationReport:
    issues: list[ValidationIssue] = field(default_factory=list)
    fixed_count: int = 0
    categories_checked: int = 0
    courses_checked: int = 0
    lessons_checked: int = 0
    errors_count: int = 0
    duration_ms: float = 0.0

    # Алиасы для совместимости
    @property
    def scanned_categories(self) -> int:
        return self.categories_checked

    @property
    def scanned_courses(self) -> int:
        return self.courses_checked

    @property
    def scanned_lessons(self) -> int:
        return self.lessons_checked

    def to_dict(self) -> dict[str, Any]:
        return {
            "fixed_count": self.fixed_count,
            "errors_count": self.errors_count,
            "categories_checked": self.categories_checked,
            "courses_checked": self.courses_checked,
            "lessons_checked": self.lessons_checked,
            "duration_ms": round(self.duration_ms, 2),
            "issues": [
                {"path": i.path, "issue": i.issue, "fixed": i.fixed, "action": i.action}
                for i in self.issues
            ],
        }


def sanitize_name(name: str) -> str:
    """Убрать недопустимые символы из имени."""
    cleaned = _FORBIDDEN_NAME_CHARS.sub("_", (name or "").strip())
    return cleaned or "unnamed"


sanitize_folder_name = sanitize_name  # alias


def parse_media_tags(text: str) -> list[dict[str, Any]]:
    """Разобрать текст на блоки text/image/video/file по тегам."""
    blocks: list[dict[str, Any]] = []
    remaining = text or ""
    pattern_list = [
        (_RE_IMAGE, "image"),
        (_RE_VIDEO, "video"),
        (_RE_FILE, "file"),
    ]
    # Простой последовательный парсинг по строкам
    for line in remaining.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        matched = False
        for pattern, mtype in pattern_list:
            m = pattern.fullmatch(stripped) or pattern.search(stripped)
            if m and m.group(0) in stripped:
                name = m.group(1).strip()
                blocks.append({"type": mtype, "name": name, "content": name})
                before = pattern.sub("", stripped).strip()
                if before:
                    blocks.insert(-1, {"type": "text", "name": "", "content": before})
                matched = True
                break
        if not matched:
            blocks.append({"type": "text", "name": "", "content": stripped})
    return blocks


def split_test_blocks(text: str) -> list[dict[str, str]]:
    """Разделить текст на части text/test по маркерам."""
    parts: list[dict[str, str]] = []
    current: list[str] = []
    mode = "text"
    for line in (text or "").splitlines():
        if _TEST_START in line:
            if current:
                parts.append({"type": mode, "content": "\n".join(current)})
                current = []
            mode = "test"
            rest = line.split(_TEST_START, 1)[-1].strip()
            if rest:
                current.append(rest)
            continue
        if _TEST_END in line:
            before = line.split(_TEST_END, 1)[0].strip()
            if before:
                current.append(before)
            if current:
                parts.append({"type": "test", "content": "\n".join(current)})
                current = []
            mode = "text"
            rest = line.split(_TEST_END, 1)[-1].strip()
            if rest:
                current.append(rest)
            continue
        current.append(line)
    if current:
        parts.append({"type": mode, "content": "\n".join(current)})
    return parts


def get_content_cache_version() -> int:
    with _cache_lock:
        return _content_cache_version


def bump_content_cache() -> int:
    global _content_cache_version
    with _cache_lock:
        _content_cache_version += 1
        return _content_cache_version


def _read_json(path: Path) -> Optional[dict]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _next_id(existing: set[int], start: int = 1) -> int:
    n = start
    while n in existing:
        n += 1
    return n


def _collect_existing_ids(base: Path) -> tuple[set[int], set[int], set[int]]:
    cat_ids: set[int] = set()
    course_ids: set[int] = set()
    lesson_ids: set[int] = set()
    if not base.exists():
        return cat_ids, course_ids, lesson_ids
    for cat_dir in base.iterdir():
        if not cat_dir.is_dir() or not cat_dir.name.startswith("category-"):
            continue
        cfg = _read_json(cat_dir / "config.json")
        if cfg and isinstance(cfg.get("id"), int):
            cat_ids.add(cfg["id"])
        for course_dir in cat_dir.iterdir():
            if not course_dir.is_dir() or not course_dir.name.startswith("course-"):
                continue
            cc = _read_json(course_dir / "config.json")
            if cc and isinstance(cc.get("id"), int):
                course_ids.add(cc["id"])
            for lesson_dir in course_dir.iterdir():
                if not lesson_dir.is_dir() or not lesson_dir.name.startswith("lesson-"):
                    continue
                lc = _read_json(lesson_dir / "config.json")
                if lc and isinstance(lc.get("id"), int):
                    lesson_ids.add(lc["id"])
    return cat_ids, course_ids, lesson_ids


def _title_from_folder(folder_name: str, prefix: str) -> str:
    slug = folder_name[len(prefix):] if folder_name.startswith(prefix) else folder_name
    return slug.replace("-", " ").strip().title() or folder_name


def generate_blocks_from_texts(lesson_dir: Path) -> list[dict]:
    """Сгенерировать blocks.json из файлов texts/block-N.txt."""
    texts_dir = lesson_dir / "texts"
    blocks: list[dict] = []
    if not texts_dir.is_dir():
        return blocks

    def _sort_key(p: Path) -> int:
        m = re.search(r"block-(\d+)", p.stem)
        return int(m.group(1)) if m else 0

    text_files = sorted(texts_dir.glob("block-*.txt"), key=_sort_key)
    order = 1
    for tf in text_files:
        m = re.search(r"block-(\d+)", tf.stem)
        if not m:
            continue
        block_id = int(m.group(1))
        content = tf.read_text(encoding="utf-8")
        block_type = "heading" if content.lstrip().startswith("#") else "text"
        blocks.append({
            "id": block_id,
            "block_type": block_type,
            "order": order,
            "content": {"text": ""},
        })
        order += 1
    return blocks


def _ensure_test_block_dirs(lesson_dir: Path, block_id: int, fix: bool) -> Optional[ValidationIssue]:
    test_dir = lesson_dir / "tests" / f"block-{block_id}"
    cfg_path = test_dir / "config.json"
    if cfg_path.exists():
        return None
    rel = str(test_dir.relative_to(get_base_categories_data_path()))
    if not fix:
        return ValidationIssue(rel, "Отсутствует config.json теста", fixed=False)
    test_dir.mkdir(parents=True, exist_ok=True)
    write_test_config(str(test_dir), FsTestConfig(title="Тест", enabled=True))
    qdir = test_dir / "questions"
    qdir.mkdir(exist_ok=True)
    (qdir / "q001.txt").write_text(
        "Q: Вопрос пока не добавлен\nA) Да\nB) Нет\nPOINTS: 1\nTYPE: single\nCORRECT: A\n",
        encoding="utf-8",
    )
    return ValidationIssue(rel, "Отсутствовал config.json теста", fixed=True, action="created_test_config")


def _validate_lesson(lesson_dir: Path, fix: bool, report: ValidationReport) -> None:
    report.lessons_checked += 1
    rel_base = str(lesson_dir.relative_to(get_base_categories_data_path()))

    cfg_path = lesson_dir / "config.json"
    cfg = _read_json(cfg_path)
    if not cfg:
        if fix:
            title = _title_from_folder(lesson_dir.name, "lesson-")
            _, _, lesson_ids = _collect_existing_ids(Path(get_base_categories_data_path()))
            new_cfg = {"id": _next_id(lesson_ids), "title": title, **DEFAULT_LESSON_CONFIG}
            _write_json(cfg_path, new_cfg)
            report.issues.append(ValidationIssue(rel_base, "Отсутствовал config.json", True, "created_config"))
            report.fixed_count += 1
            cfg = new_cfg
        else:
            report.issues.append(ValidationIssue(rel_base, "Отсутствует config.json", False))
            report.errors_count += 1
            return

    for sub in ("texts", "images", "videos", "files", "tests"):
        sub_path = lesson_dir / sub
        if not sub_path.exists() and fix:
            sub_path.mkdir(parents=True, exist_ok=True)
            report.issues.append(ValidationIssue(f"{rel_base}/{sub}", f"Создана папка {sub}", True, "mkdir"))
            report.fixed_count += 1

    blocks_path = lesson_dir / "blocks.json"
    blocks = read_blocks(lesson_dir)
    if not blocks_path.exists() or not blocks:
        generated = generate_blocks_from_texts(lesson_dir)
        if generated and fix:
            write_blocks(lesson_dir, generated)
            blocks = generated
            report.issues.append(
                ValidationIssue(f"{rel_base}/blocks.json", "Сгенерирован из texts/", True, "generated_blocks")
            )
            report.fixed_count += 1
        elif not blocks_path.exists():
            if fix:
                write_blocks(lesson_dir, [])
                report.issues.append(
                    ValidationIssue(f"{rel_base}/blocks.json", "Создан пустой blocks.json", True, "created_empty")
                )
                report.fixed_count += 1
            else:
                report.issues.append(ValidationIssue(f"{rel_base}/blocks.json", "Отсутствует blocks.json", False))
                report.errors_count += 1

    for b in blocks:
        bid = b.get("id")
        btype = (b.get("block_type") or "").strip()
        if not isinstance(bid, int):
            continue
        if btype in ("text", "heading"):
            tf = lesson_dir / "texts" / f"block-{bid}.txt"
            if not tf.exists():
                msg = f"Нет файла texts/block-{bid}.txt для блока {bid}"
                if fix:
                    tf.parent.mkdir(parents=True, exist_ok=True)
                    tf.write_text("", encoding="utf-8")
                    report.issues.append(
                        ValidationIssue(str(tf.relative_to(get_base_categories_data_path())), msg, True, "created_text")
                    )
                    report.fixed_count += 1
                else:
                    report.issues.append(ValidationIssue(f"{rel_base}/blocks.json", msg, False))
                    report.errors_count += 1
        elif btype == "test":
            issue = _ensure_test_block_dirs(lesson_dir, bid, fix)
            if issue:
                report.issues.append(issue)
                if issue.fixed:
                    report.fixed_count += 1
                else:
                    report.errors_count += 1


def _validate_course(course_dir: Path, fix: bool, report: ValidationReport) -> None:
    report.courses_checked += 1
    rel_base = str(course_dir.relative_to(get_base_categories_data_path()))
    cfg_path = course_dir / "config.json"
    cfg = _read_json(cfg_path)
    if not cfg:
        if fix:
            title = _title_from_folder(course_dir.name, "course-")
            _, course_ids, _ = _collect_existing_ids(Path(get_base_categories_data_path()))
            new_cfg = {"id": _next_id(course_ids), "title": title, **DEFAULT_COURSE_CONFIG}
            _write_json(cfg_path, new_cfg)
            report.issues.append(ValidationIssue(rel_base, "Отсутствовал config.json", True, "created_config"))
            report.fixed_count += 1
        else:
            report.issues.append(ValidationIssue(rel_base, "Отсутствует config.json", False))
            report.errors_count += 1
            return

    for lesson_dir in sorted(course_dir.iterdir()):
        if lesson_dir.is_dir() and lesson_dir.name.startswith("lesson-"):
            _validate_lesson(lesson_dir, fix, report)

    if fix and cfg:
        lesson_count = sum(1 for e in course_dir.iterdir() if e.is_dir() and e.name.startswith("lesson-"))
        updated = dict(cfg)
        if updated.get("total_lessons") != lesson_count:
            updated["total_lessons"] = lesson_count
            updated["updated_at"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
            _write_json(cfg_path, updated)


def _validate_category(cat_dir: Path, fix: bool, report: ValidationReport) -> None:
    report.categories_checked += 1
    rel_base = str(cat_dir.relative_to(get_base_categories_data_path()))
    cfg_path = cat_dir / "config.json"
    cfg = _read_json(cfg_path)
    if not cfg:
        if fix:
            title = _title_from_folder(cat_dir.name, "category-")
            cat_ids, _, _ = _collect_existing_ids(Path(get_base_categories_data_path()))
            new_cfg = {"id": _next_id(cat_ids), "title": title, **DEFAULT_CATEGORY_CONFIG}
            _write_json(cfg_path, new_cfg)
            report.issues.append(ValidationIssue(rel_base, "Отсутствовал config.json", True, "created_config"))
            report.fixed_count += 1
        else:
            report.issues.append(ValidationIssue(rel_base, "Отсутствует config.json", False))
            report.errors_count += 1
            return

    for course_dir in sorted(cat_dir.iterdir()):
        if course_dir.is_dir() and course_dir.name.startswith("course-"):
            _validate_course(course_dir, fix, report)


def validate_and_fix_structure(fix: bool = True) -> ValidationReport:
    t0 = time.perf_counter()
    report = ValidationReport()
    ensure_categories_data_directory()
    base = Path(get_base_categories_data_path())
    if base.exists():
        for cat_dir in sorted(base.iterdir()):
            if cat_dir.is_dir() and cat_dir.name.startswith("category-"):
                _validate_category(cat_dir, fix, report)
    report.duration_ms = (time.perf_counter() - t0) * 1000
    return report


def reload_content() -> dict[str, Any]:
    report = validate_and_fix_structure(fix=True)
    version = bump_content_cache()
    return {"ok": True, "cache_version": version, "validation": report.to_dict()}


def maybe_git_commit(message: str) -> Optional[str]:
    root = Path(get_base_categories_data_path())
    git_dir = None
    for parent in [root, *root.parents]:
        if (parent / ".git").exists():
            git_dir = parent
            break
    if not git_dir:
        return None
    try:
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(git_dir),
            capture_output=True,
            text=True,
            timeout=30,
        )
        if not status.stdout.strip():
            return None
        subprocess.run(["git", "add", "-A"], cwd=str(git_dir), check=True, timeout=60)
        result = subprocess.run(
            ["git", "commit", "-m", message],
            cwd=str(git_dir),
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode == 0:
            rev = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd=str(git_dir),
                capture_output=True,
                text=True,
                timeout=10,
            )
            return (rev.stdout or "").strip() or "committed"
    except Exception as exc:
        logger.warning("Git autocommit skipped: %s", exc)
    return None
