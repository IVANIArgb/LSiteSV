"""Тесты парсера Word-документов."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

try:
    from docx import Document
    HAS_DOCX = True
except ImportError:
    HAS_DOCX = False

pytestmark = pytest.mark.skipif(not HAS_DOCX, reason="python-docx не установлен")


def _make_docx(path: Path, paragraphs: list[str]) -> None:
    doc = Document()
    for p in paragraphs:
        doc.add_paragraph(p)
    doc.save(str(path))


@pytest.fixture
def lesson_with_docx(temp_content_root):
    lesson = temp_content_root / "category-c" / "course-c" / "lesson-w"
    for sub in ("texts", "images", "videos", "files", "tests"):
        (lesson / sub).mkdir(parents=True)
    (lesson / "config.json").write_text(
        json.dumps({"id": 1, "title": "Word урок", "course_id": 1}),
        encoding="utf-8",
    )
    return lesson


class TestWordParser:
    def test_parse_basic_text(self, lesson_with_docx):
        _make_docx(lesson_with_docx / "lesson.docx", [
            "# Заголовок урока",
            "Основной текст урока.",
        ])
        from scripts.parse_word_lesson import parse_lesson_from_docx

        summary = parse_lesson_from_docx(lesson_with_docx)
        assert summary["text_blocks"] >= 1
        assert (lesson_with_docx / "blocks.json").exists()
        blocks = json.loads((lesson_with_docx / "blocks.json").read_text(encoding="utf-8"))
        assert len(blocks["blocks"]) >= 1

    def test_parse_media_tags(self, lesson_with_docx):
        _make_docx(lesson_with_docx / "lesson.docx", [
            "Текст перед картинкой",
            "[IMAGE: schema.png]",
        ])
        from scripts.parse_word_lesson import parse_lesson_from_docx

        summary = parse_lesson_from_docx(lesson_with_docx)
        assert summary["media_blocks"] == 1
        assert (lesson_with_docx / "images" / "schema.png").exists()

    def test_parse_test_block(self, lesson_with_docx):
        _make_docx(lesson_with_docx / "lesson.docx", [
            "=== ТЕСТ НАЧАЛО ===",
            "Q: Столица России?",
            "A) Москва",
            "B) Париж",
            "TYPE: single",
            "CORRECT: A",
            "POINTS: 1",
            "=== ТЕСТ КОНЕЦ ===",
        ])
        from scripts.parse_word_lesson import parse_lesson_from_docx

        summary = parse_lesson_from_docx(lesson_with_docx)
        assert summary["test_blocks"] == 1
        assert summary["questions"] >= 1
        test_dir = lesson_with_docx / "tests" / "block-1"
        assert (test_dir / "config.json").exists()
        assert (test_dir / "questions" / "q001.txt").exists()

    def test_missing_docx_raises(self, lesson_with_docx):
        from scripts.parse_word_lesson import parse_lesson_from_docx

        with pytest.raises(FileNotFoundError, match="lesson.docx"):
            parse_lesson_from_docx(lesson_with_docx)
