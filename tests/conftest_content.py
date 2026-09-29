"""Фикстуры для тестов контента LMS."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def temp_content_root(monkeypatch):
    """Временная папка контента, удаляется после теста."""
    tmp = tempfile.mkdtemp(prefix="lms_test_content_")
    import backend.utils.categories_data_sync as cds

    monkeypatch.setattr(cds, "BASE_CATEGORIES_DATA_PATH", tmp)
    monkeypatch.setenv("CONTENT_ROOT_DIR", tmp)
    yield Path(tmp)
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture
def sample_category(temp_content_root):
    """Одна категория с config.json."""
    cat_dir = temp_content_root / "category-test"
    cat_dir.mkdir(parents=True)
    cfg = {"id": 1, "title": "Тестовая категория", "is_active": True, "order": 1}
    (cat_dir / "config.json").write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
    return cat_dir


@pytest.fixture
def sample_lesson_broken(temp_content_root, sample_category):
    """Урок без blocks.json и с битым block-5 в blocks."""
    course_dir = sample_category / "course-demo"
    course_dir.mkdir()
    (course_dir / "config.json").write_text(
        json.dumps({"id": 1, "title": "Демо курс", "category_id": 1, "is_active": True}, ensure_ascii=False),
        encoding="utf-8",
    )
    lesson_dir = course_dir / "lesson-intro"
    lesson_dir.mkdir()
    (lesson_dir / "config.json").write_text(
        json.dumps({"id": 1, "title": "Введение", "course_id": 1, "is_active": True}, ensure_ascii=False),
        encoding="utf-8",
    )
    (lesson_dir / "texts").mkdir()
    (lesson_dir / "texts" / "block-1.txt").write_text("Привет", encoding="utf-8")
    blocks = {"blocks": [{"id": 1, "block_type": "text", "order": 1}, {"id": 5, "block_type": "text", "order": 2}]}
    (lesson_dir / "blocks.json").write_text(json.dumps(blocks), encoding="utf-8")
    return lesson_dir
