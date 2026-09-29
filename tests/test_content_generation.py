"""Тесты генерации конфигов, создания папок и парсинга тегов."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.content_validator import (
    generate_blocks_from_texts,
    parse_media_tags,
    sanitize_name,
    split_test_blocks,
    validate_and_fix_structure,
)


class TestSanitizeName:
    def test_removes_forbidden_chars(self):
        assert sanitize_name('test\\/:*?"<>|name') == "test_________name"

    def test_empty_becomes_unnamed(self):
        assert sanitize_name("") == "unnamed"
        assert sanitize_name("   ") == "unnamed"

    def test_cyrillic_preserved(self):
        assert sanitize_name("Курс безопасности") == "Курс безопасности"


class TestMediaTags:
    def test_image_tag(self):
        blocks = parse_media_tags("Текст\n[IMAGE: pic.png]\nЕщё текст")
        types = [b["type"] for b in blocks]
        assert "image" in types
        assert "text" in types
        img = next(b for b in blocks if b["type"] == "image")
        assert img["name"] == "pic.png"

    def test_video_and_file(self):
        blocks = parse_media_tags("[VIDEO: v.mp4]\n[FILE: doc.pdf]")
        assert len(blocks) == 2
        assert blocks[0]["type"] == "video"
        assert blocks[1]["type"] == "file"


class TestTestBlocks:
    def test_split_test_block(self):
        text = "Введение\n=== ТЕСТ НАЧАЛО ===\nQ: Вопрос?\nA) Да\n=== ТЕСТ КОНЕЦ ===\nЗаключение"
        parts = split_test_blocks(text)
        types = [p["type"] for p in parts]
        assert "test" in types
        test_part = next(p for p in parts if p["type"] == "test")
        assert "Q:" in test_part["content"]


class TestGenerateBlocksFromTexts:
    def test_from_text_files(self, temp_content_root):
        lesson = temp_content_root / "lesson-a"
        texts = lesson / "texts"
        texts.mkdir(parents=True)
        (texts / "block-1.txt").write_text("# Заголовок", encoding="utf-8")
        (texts / "block-2.txt").write_text("Текст урока", encoding="utf-8")
        blocks = generate_blocks_from_texts(lesson)
        assert len(blocks) == 2
        assert blocks[0]["block_type"] == "heading"
        assert blocks[1]["block_type"] == "text"


class TestValidateAndFix:
    def test_creates_missing_config(self, temp_content_root):
        cat = temp_content_root / "category-new"
        cat.mkdir()
        report = validate_and_fix_structure(fix=True)
        assert (cat / "config.json").exists()
        assert report.fixed_count >= 1

    def test_fixes_missing_text_file(self, sample_lesson_broken):
        report = validate_and_fix_structure(fix=True)
        missing = sample_lesson_broken / "texts" / "block-5.txt"
        assert missing.exists()
        assert report.fixed_count >= 1

    def test_dry_run_no_fix(self, sample_lesson_broken):
        report = validate_and_fix_structure(fix=False)
        assert report.errors_count >= 1
        assert not (sample_lesson_broken / "texts" / "block-5.txt").exists()


class TestFolderCreation:
    def test_create_category_structure(self, temp_content_root):
        from scripts.lms_content_manager import cmd_create_category, cmd_create_course, cmd_create_lesson

        cmd_create_category("Безопасность")
        cmd_create_course("Безопасность", "Основы")
        cmd_create_lesson("Безопасность", "Основы", "Урок 1")

        base = temp_content_root
        cats = list(base.glob("category-*"))
        assert len(cats) == 1
        courses = list(cats[0].glob("course-*"))
        assert len(courses) == 1
        lessons = list(courses[0].glob("lesson-*"))
        assert len(lessons) == 1
        assert (lessons[0] / "blocks.json").exists()
        assert (lessons[0] / "config.json").exists()
