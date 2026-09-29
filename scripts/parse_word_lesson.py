#!/usr/bin/env python3
"""Парсер Word-документов lesson.docx для уроков LMS."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.content_validator import split_test_blocks

_RE_IMAGE = re.compile(r"\[IMAGE:\s*([^\]]+)\]", re.IGNORECASE)
_RE_VIDEO = re.compile(r"\[VIDEO:\s*([^\]]+)\]", re.IGNORECASE)
_RE_FILE = re.compile(r"\[FILE:\s*([^\]]+)\]", re.IGNORECASE)


def _require_docx():
    try:
        from docx import Document
        return Document
    except ImportError as exc:
        raise ImportError("Установите python-docx: pip install python-docx") from exc


def _parse_test_questions(lines: list[str]) -> list[str]:
    questions: list[str] = []
    buf: list[str] = []
    for line in lines:
        if line.upper().startswith("Q:") and buf:
            questions.append("\n".join(buf))
            buf = [line]
        else:
            buf.append(line)
    if buf:
        questions.append("\n".join(buf))
    return questions


def parse_lesson_from_docx(lesson_dir: Path) -> dict[str, Any]:
    """
    Прочитать lesson.docx и собрать blocks.json, texts/, tests/.
    Возвращает сводку: text_blocks, media_blocks, test_blocks, questions.
    """
    lesson_dir = Path(lesson_dir)
    docx_path = lesson_dir / "lesson.docx"
    if not docx_path.exists():
        raise FileNotFoundError(f"Файл lesson.docx не найден в {lesson_dir}")

    Document = _require_docx()
    doc = Document(str(docx_path))
    all_lines = [p.text.strip() for p in doc.paragraphs if (p.text or "").strip()]
    full_text = "\n".join(all_lines)
    segments = split_test_blocks(full_text)

    texts_dir = lesson_dir / "texts"
    images_dir = lesson_dir / "images"
    videos_dir = lesson_dir / "videos"
    files_dir = lesson_dir / "files"
    tests_base = lesson_dir / "tests"
    for d in (texts_dir, images_dir, videos_dir, files_dir, tests_base):
        d.mkdir(parents=True, exist_ok=True)

    blocks: list[dict[str, Any]] = []
    block_id = 1
    order = 1
    text_blocks = media_blocks = test_blocks = questions_total = 0

    for seg in segments:
        seg_type = seg["type"]
        content = seg["content"]
        if seg_type == "text":
            for line in content.splitlines():
                stripped = line.strip()
                if not stripped:
                    continue
                for pattern, mtype, target_dir in (
                    (_RE_IMAGE, "image", images_dir),
                    (_RE_VIDEO, "video", videos_dir),
                    (_RE_FILE, "file", files_dir),
                ):
                    m = pattern.search(stripped)
                    if m:
                        name = m.group(1).strip()
                        safe = re.sub(r'[\\/:*?"<>|]', "_", name)
                        fp = target_dir / safe
                        fp.parent.mkdir(parents=True, exist_ok=True)
                        if not fp.exists():
                            fp.write_bytes(b"")
                        blocks.append({
                            "id": block_id,
                            "block_type": mtype,
                            "order": order,
                            "content": {"filename": safe, "caption": name},
                        })
                        block_id += 1
                        order += 1
                        media_blocks += 1
                        stripped = pattern.sub("", stripped).strip()
                if stripped:
                    block_type = "heading" if stripped.startswith("#") else "text"
                    tf = texts_dir / f"block-{block_id}.txt"
                    tf.write_text(stripped, encoding="utf-8")
                    blocks.append({
                        "id": block_id,
                        "block_type": block_type,
                        "order": order,
                        "content": {"text": ""},
                    })
                    block_id += 1
                    order += 1
                    text_blocks += 1
        else:
            test_title = "Тест"
            lines = content.splitlines()
            for ln in lines:
                if ln.upper().startswith("TITLE:"):
                    test_title = ln.split(":", 1)[1].strip()
                    break
            questions = _parse_test_questions(lines)
            test_dir = tests_base / f"block-{block_id}"
            qdir = test_dir / "questions"
            qdir.mkdir(parents=True, exist_ok=True)
            (test_dir / "config.json").write_text(
                json.dumps({
                    "title": test_title,
                    "enabled": True,
                    "pass_percent": 70,
                    "limit_attempts": False,
                    "max_attempts": None,
                    "test_type": "permanent",
                    "shuffle_questions": False,
                    "shuffle_options": False,
                    "time_limit_seconds": None,
                }, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            if not questions:
                questions = [
                    "Q: Вопрос не распознан\nA) Да\nB) Нет\nPOINTS: 1\nTYPE: single\nCORRECT: A\n"
                ]
            for qi, qtext in enumerate(questions, 1):
                (qdir / f"q{qi:03d}.txt").write_text(qtext.strip() + "\n", encoding="utf-8")
            questions_total += len(questions)
            blocks.append({
                "id": block_id,
                "block_type": "test",
                "order": order,
                "content": {"title": test_title},
            })
            block_id += 1
            order += 1
            test_blocks += 1

    (lesson_dir / "blocks.json").write_text(
        json.dumps({"blocks": blocks}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {
        "text_blocks": text_blocks,
        "media_blocks": media_blocks,
        "test_blocks": test_blocks,
        "questions": questions_total,
        "total_blocks": len(blocks),
    }


def parse_lesson_docx(lesson_dir: Path) -> int:
    """CLI-обёртка: 0 при успехе, 1 при ошибке."""
    try:
        summary = parse_lesson_from_docx(lesson_dir)
        print(f"Готово: {summary['total_blocks']} блоков")
        return 0
    except FileNotFoundError as exc:
        print(f"ОШИБКА: {exc}")
        return 1
    except Exception as exc:
        print(f"ОШИБКА: {exc}")
        return 1


def main() -> int:
    if len(sys.argv) < 2:
        print("Использование: python parse_word_lesson.py <папка_урока>")
        return 1
    return parse_lesson_docx(Path(sys.argv[1]))


if __name__ == "__main__":
    sys.exit(main())
