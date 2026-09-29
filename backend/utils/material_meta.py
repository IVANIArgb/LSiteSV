"""Метаданные материалов (категория, курс, урок) для UI «Информация»."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from backend.utils.content_fs import (
    find_category,
    find_course,
    find_lesson,
    to_public_dict,
)
from database.models import Category, Course, Lesson, NewsEvent, User

_MATERIAL_MODELS = {
    "category": Category,
    "course": Course,
    "lesson": Lesson,
}

_EVENT_TYPES = {
    "category": "category_created",
    "course": "course_created",
    "lesson": "lesson_created",
}

_META_ID_KEYS = {
    "category": "category_id",
    "course": "course_id",
    "lesson": "lesson_id",
}

_TYPE_LABELS = {
    "category": "Категория",
    "course": "Курс",
    "lesson": "Урок",
}


def _iso_from_dt(value) -> Optional[str]:
    if not value:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _file_mtime_iso(path: Path) -> Optional[str]:
    try:
        if path.is_file():
            ts = path.stat().st_mtime
            return datetime.fromtimestamp(ts, tz=timezone.utc).replace(microsecond=0).isoformat()
    except OSError:
        pass
    return None


def _creator_from_news(session: Session, material_type: str, material_id: int) -> Dict[str, Optional[str]]:
    event_type = _EVENT_TYPES.get(material_type)
    meta_key = _META_ID_KEYS.get(material_type)
    if not event_type or not meta_key:
        return {"created_by": None, "created_by_username": None, "created_at": None}

    events = (
        session.query(NewsEvent)
        .filter(NewsEvent.event_type == event_type)
        .order_by(NewsEvent.created_at.asc())
        .all()
    )
    for event in events:
        meta = None
        if event.meta:
            try:
                meta = json.loads(event.meta)
            except Exception:
                meta = None
        if not isinstance(meta, dict) or meta.get(meta_key) != material_id:
            continue
        user = session.query(User).filter(User.id == event.created_by).first()
        name = None
        username = None
        if user:
            name = (user.full_name or user._get_full_name_from_parts() or user.username or "").strip() or None
            username = (user.username or "").strip() or None
        return {
            "created_by": name,
            "created_by_username": username,
            "created_at": _iso_from_dt(event.created_at),
        }
    return {"created_by": None, "created_by_username": None, "created_at": None}


def _load_fs_material(material_type: str, material_id: int):
    if material_type == "category":
        item = find_category(material_id)
        if not item:
            return None
        return item, to_public_dict(item.cfg, {"id": item.id, "title": item.title}), item.path / "config.json"
    if material_type == "course":
        item = find_course(material_id)
        if not item:
            return None
        return (
            item,
            to_public_dict(item.cfg, {"id": item.id, "title": item.title, "category_id": item.category_id}),
            item.path / "config.json",
        )
    if material_type == "lesson":
        item = find_lesson(material_id)
        if not item:
            return None
        return (
            item,
            to_public_dict(
                item.cfg,
                {"id": item.id, "title": item.title, "course_id": item.course_id, "category_id": item.category_id},
            ),
            item.path / "config.json",
        )
    return None


def get_material_info(session: Session, material_type: str, material_id: int) -> Optional[Dict[str, Any]]:
    """Собрать описание, даты и автора материала."""
    material_type = (material_type or "").strip().lower()
    if material_type not in _MATERIAL_MODELS:
        return None

    loaded = _load_fs_material(material_type, material_id)
    if not loaded:
        return None

    _item, cfg, config_path = loaded
    model_cls = _MATERIAL_MODELS[material_type]
    db_row = session.query(model_cls).filter(model_cls.id == material_id).first()

    news_meta = _creator_from_news(session, material_type, material_id)

    created_at = cfg.get("created_at") or (db_row and _iso_from_dt(db_row.created_at)) or news_meta.get("created_at")
    if not created_at:
        created_at = _file_mtime_iso(config_path)

    updated_at = cfg.get("updated_at") or (db_row and _iso_from_dt(db_row.updated_at))

    created_by = cfg.get("created_by_name") or cfg.get("created_by") or news_meta.get("created_by")
    created_by_username = cfg.get("created_by_username") or news_meta.get("created_by_username")

    description = cfg.get("description") or (db_row.description if db_row else None) or ""

    return {
        "type": material_type,
        "type_label": _TYPE_LABELS[material_type],
        "id": material_id,
        "title": cfg.get("title") or (db_row.title if db_row else ""),
        "description": description or "",
        "created_at": created_at,
        "updated_at": updated_at,
        "created_by": created_by,
        "created_by_username": created_by_username,
    }


def creator_fields_for_config(user: User) -> Dict[str, str]:
    """Поля автора/даты для записи в config.json при создании."""
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    username = (user.username or "").strip()
    display = (user.full_name or user._get_full_name_from_parts() or username).strip()
    return {
        "created_at": now,
        "updated_at": now,
        "created_by": display or username,
        "created_by_name": display or username,
        "created_by_username": username,
    }
