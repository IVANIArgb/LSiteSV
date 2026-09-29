"""Интеграционные тесты API валидации и перезагрузки контента."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest


@pytest.fixture
def admin_client(app, mock_kerberos_and_ad, sample_admin, temp_content_root):
    """Клиент с правами admin и изолированным контентом."""
    return app.test_client()


class TestValidateStructureAPI:
    def test_validate_requires_auth(self, client, temp_content_root):
        resp = client.get("/api/admin/validate-structure")
        assert resp.status_code == 401

    def test_validate_as_admin(self, admin_client, temp_content_root):
        # Создаём битую структуру
        cat = temp_content_root / "category-api"
        cat.mkdir()
        resp = admin_client.post(
            "/api/admin/validate-structure",
            json={"fix": True},
            headers={"Authorization": "Negotiate FAKE_TOKEN_ADMIN"},
        )
        assert resp.status_code in (200, 207)
        data = resp.get_json()
        assert "categories_checked" in data
        assert (cat / "config.json").exists()

    def test_reload_content(self, admin_client, temp_content_root):
        resp = admin_client.post(
            "/api/admin/reload-content",
            json={"validate": True},
            headers={"Authorization": "Negotiate FAKE_TOKEN_ADMIN"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get("ok") is True
        assert "cache_version" in data


class TestPerformanceManyLessons:
    def test_100_lessons_validation_under_2s(self, temp_content_root):
        """100 уроков — валидация должна уложиться в 2 секунды."""
        from backend.content_validator import validate_and_fix_structure

        cat = temp_content_root / "category-perf"
        cat.mkdir()
        (cat / "config.json").write_text(
            json.dumps({"id": 1, "title": "Perf", "is_active": True}),
            encoding="utf-8",
        )
        course = cat / "course-perf"
        course.mkdir()
        (course / "config.json").write_text(
            json.dumps({"id": 1, "title": "Perf Course", "category_id": 1, "is_active": True}),
            encoding="utf-8",
        )
        for i in range(1, 101):
            lesson = course / f"lesson-{i}"
            lesson.mkdir()
            (lesson / "config.json").write_text(
                json.dumps({"id": i, "title": f"Урок {i}", "course_id": 1, "is_active": True}),
                encoding="utf-8",
            )
            (lesson / "texts").mkdir()
            (lesson / "texts" / "block-1.txt").write_text(f"Текст {i}", encoding="utf-8")

        t0 = time.perf_counter()
        report = validate_and_fix_structure(fix=True)
        elapsed = time.perf_counter() - t0
        assert report.lessons_checked == 100
        assert elapsed < 2.0, f"Валидация 100 уроков заняла {elapsed:.2f}с (> 2с)"
