"""Тесты метаданных материалов."""
import json
from pathlib import Path

from backend.utils.material_meta import get_material_info, creator_fields_for_config
from database.models import User, NewsEvent


class TestMaterialMeta:
    def test_creator_fields_for_config(self):
        user = User(username="admin", full_name="Админ Тест")
        fields = creator_fields_for_config(user)
        assert fields["created_by_username"] == "admin"
        assert "created_at" in fields

    def test_get_material_info_from_config_and_news(self, tmp_path, monkeypatch):
        base = tmp_path / "content"
        cat_dir = base / "category-test"
        cat_dir.mkdir(parents=True)
        (cat_dir / "config.json").write_text(
            json.dumps(
                {
                    "id": 1,
                    "title": "Тест",
                    "description": "Описание категории",
                    "type": "category",
                    "created_at": "2025-01-15T10:00:00+00:00",
                    "created_by_name": "Автор из config",
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        monkeypatch.setattr(
            "backend.utils.categories_data_sync.get_base_categories_data_path",
            lambda: str(base),
        )
        monkeypatch.setattr(
            "backend.utils.content_fs.get_base_categories_data_path",
            lambda: str(base),
        )

        from database.models import db_manager, Category

        session = db_manager.get_session()
        try:
            session.query(NewsEvent).delete()
            session.query(Category).delete()
            user = User(username="creator_meta_test", full_name="Создатель")
            session.add(user)
            session.flush()
            session.add(
                NewsEvent(
                    event_type="category_created",
                    title="Создана",
                    meta=json.dumps({"category_id": 1}),
                    created_by=user.id,
                )
            )
            session.add(Category(id=1, title="Тест", description="Из БД"))
            session.commit()

            info = get_material_info(session, "category", 1)
            assert info is not None
            assert info["title"] == "Тест"
            assert info["description"] == "Описание категории"
            assert info["created_by"] == "Автор из config"
        finally:
            session.close()
