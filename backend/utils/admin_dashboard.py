"""Данные для главной страницы админ-панели."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from backend.utils.content_fs import load_categories as fs_load_categories
from backend.utils.content_fs import load_courses as fs_load_courses
from database.models import Course, DeletedObject, NewsEvent, Question, User, UserCourseProgress

_EVENT_LABELS = {
    "category_created": "Категория",
    "category_updated": "Категория",
    "course_created": "Курс",
    "course_updated": "Курс",
    "lesson_created": "Урок",
    "lesson_updated": "Урок",
    "global_test_created": "Тест",
    "global_test_updated": "Тест",
    "manual": "Новость",
}


def _parse_cfg_ts(cfg: dict) -> datetime:
    for key in ("updated_at", "created_at"):
        raw = cfg.get(key)
        if not raw:
            continue
        try:
            s = str(raw).replace("Z", "+00:00")
            dt = datetime.fromisoformat(s)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except (TypeError, ValueError):
            continue
    return datetime.min.replace(tzinfo=timezone.utc)


def _parse_meta(raw: Any) -> Optional[dict]:
    if isinstance(raw, dict):
        return raw
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else None
    except (TypeError, ValueError, json.JSONDecodeError):
        return None


def _format_when(dt: Optional[datetime]) -> str:
    if not dt:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    delta = now - dt.astimezone(timezone.utc)
    if delta.total_seconds() < 60:
        return "только что"
    if delta.total_seconds() < 3600:
        mins = int(delta.total_seconds() // 60)
        return f"{mins} мин. назад"
    if delta.days == 0:
        hours = int(delta.total_seconds() // 3600)
        return f"{hours} ч. назад"
    if delta.days == 1:
        return "вчера"
    if delta.days < 7:
        return f"{delta.days} дн. назад"
    return dt.astimezone(timezone.utc).strftime("%d.%m.%Y %H:%M")


def _news_href(event_type: str, meta: Optional[dict]) -> str:
    meta = meta or {}
    if event_type in ("course_created", "course_updated"):
        cat_id = meta.get("category_id")
        course_id = meta.get("course_id")
        if cat_id:
            return f"/all-courses-pg?category_id={cat_id}"
        if course_id:
            return f"/all-lessons-pg?course_id={course_id}"
    if event_type in ("lesson_created", "lesson_updated"):
        lesson_id = meta.get("lesson_id")
        course_id = meta.get("course_id")
        if lesson_id:
            return f"/lessons-content-pg?lesson_id={lesson_id}"
        if course_id:
            return f"/all-lessons-pg?course_id={course_id}"
    if event_type in ("category_created", "category_updated") and meta.get("category_id"):
        return f"/all-courses-pg?category_id={meta['category_id']}"
    if event_type.startswith("global_test"):
        return "/tests-analytics-pg"
    return "/main"


def _event_subtitle(event_type: str, body: Optional[str], meta: Optional[dict]) -> str:
    if body and str(body).strip():
        text = str(body).strip()
        return text if len(text) <= 120 else text[:117] + "…"
    meta = meta or {}
    if event_type in ("course_created", "course_updated"):
        return "Изменения в структуре курса — проверьте содержимое и доступ."
    if event_type in ("lesson_created", "lesson_updated"):
        return "Обновлён учебный материал — откройте урок для проверки."
    if event_type in ("category_created", "category_updated"):
        return "Изменена категория в базе знаний."
    if event_type.startswith("global_test"):
        return "Изменения в глобальных тестах — см. аналитику."
    if event_type == "manual":
        return "Ручная публикация в ленте новостей."
    return "Системное событие платформы."


def _enrollment_counts(session: Session) -> Dict[int, int]:
    rows = (
        session.query(UserCourseProgress.course_id, func.count(UserCourseProgress.id))
        .group_by(UserCourseProgress.course_id)
        .all()
    )
    return {int(cid): int(cnt) for cid, cnt in rows}


def build_admin_dashboard(
    session: Session,
    *,
    active_limit: Optional[int] = None,
    news_limit: int = 12,
    stats_limit: Optional[int] = None,
) -> Dict[str, Any]:
    """Собрать блоки главной админ-страницы из контента и БД."""
    enrollment = _enrollment_counts(session)

    active_courses: List[dict] = []
    for cat in fs_load_categories():
        for course in fs_load_courses(cat):
            cfg = course.cfg or {}
            if cfg.get("is_active") is False:
                continue
            students = enrollment.get(course.id, 0)
            active_courses.append(
                {
                    "id": course.id,
                    "title": course.title,
                    "category_id": course.category_id,
                    "category_title": cat.title,
                    "href": f"/all-lessons-pg?course_id={course.id}",
                    "updated_at": _parse_cfg_ts(cfg).isoformat(),
                    "students_count": students,
                    "students_label": _students_label(students),
                }
            )

    active_courses.sort(key=lambda c: c["updated_at"], reverse=True)
    if active_limit is not None and active_limit > 0:
        active_courses = active_courses[:active_limit]

    course_stats: List[dict] = []
    db_courses = (
        session.query(Course)
        .options(joinedload(Course.user_progress))
        .filter(Course.is_active == True)  # noqa: E712
        .all()
    )
    for course in db_courses:
        enrolled = len(course.user_progress)
        completed = len([p for p in course.user_progress if p.is_completed])
        course_stats.append(
            {
                "id": course.id,
                "title": course.title,
                "category_id": course.category_id,
                "students_count": enrolled,
                "completed_count": completed,
                "href": f"/all-lessons-pg?course_id={course.id}",
            }
        )
    course_stats.sort(key=lambda c: (-c["students_count"], c["title"].lower()))
    if stats_limit is not None and stats_limit > 0:
        course_stats = course_stats[:stats_limit]

    week_ago = datetime.utcnow() - timedelta(days=7)
    new_users = int(session.query(func.count(User.id)).filter(User.created_at >= week_ago).scalar() or 0)
    open_questions = int(
        session.query(func.count(Question.id)).filter(Question.is_resolved == False).scalar()  # noqa: E712
        or 0
    )
    bin_count = int(session.query(func.count(DeletedObject.id)).scalar() or 0)
    total_users = int(session.query(func.count(User.id)).scalar() or 0)
    active_users = int(session.query(func.count(User.id)).filter(User.is_active == True).scalar() or 0)  # noqa: E712

    notifications: List[dict] = []

    if open_questions:
        notifications.append(
            {
                "kind": "alert",
                "label": "Вопросы",
                "title": _questions_title(open_questions),
                "subtitle": "Пользователи ждут ответа — перейдите в раздел вопросов.",
                "href": "/questions",
                "time": "",
                "priority": 0,
            }
        )

    if bin_count:
        notifications.append(
            {
                "kind": "alert",
                "label": "Корзина",
                "title": _bin_title(bin_count),
                "subtitle": "Удалённый контент можно восстановить или окончательно удалить.",
                "href": "/bin",
                "time": "",
                "priority": 1,
            }
        )

    if new_users:
        notifications.append(
            {
                "kind": "alert",
                "label": "Пользователи",
                "title": f"+{new_users} за 7 дней",
                "subtitle": f"Всего в системе {total_users} пользователей ({active_users} активных).",
                "href": "/users-info",
                "time": "",
                "priority": 2,
            }
        )

    news_items = (
        session.query(NewsEvent)
        .order_by(NewsEvent.created_at.desc(), NewsEvent.id.desc())
        .limit(max(1, news_limit))
        .all()
    )
    for ev in news_items:
        meta = _parse_meta(ev.meta)
        notifications.append(
            {
                "kind": "news",
                "label": _EVENT_LABELS.get(ev.event_type, "Событие"),
                "title": ev.title,
                "subtitle": _event_subtitle(ev.event_type, ev.body, meta),
                "href": _news_href(ev.event_type, meta),
                "time": _format_when(ev.created_at),
                "event_type": ev.event_type,
                "priority": 10,
            }
        )

    if not notifications:
        notifications.append(
            {
                "kind": "system",
                "label": "Система",
                "title": "Всё спокойно",
                "subtitle": "Нет срочных задач. Журнал событий доступен в разделе «Логи».",
                "href": "/logs",
                "time": "",
                "priority": 99,
            }
        )

    notifications.sort(key=lambda n: n.get("priority", 50))

    return {
        "active_courses": active_courses,
        "notifications": notifications,
        "course_stats": course_stats,
        "overview": {
            "active_courses_total": len(active_courses),
            "courses_with_students": sum(1 for c in course_stats if c["students_count"] > 0),
            "total_enrollments": sum(c["students_count"] for c in course_stats),
            "open_questions": open_questions,
            "bin_count": bin_count,
            "new_users_week": new_users,
            "total_users": total_users,
            "active_users": active_users,
        },
    }


def _students_label(count: int) -> str:
    n = int(count or 0)
    mod10, mod100 = n % 10, n % 100
    if mod10 == 1 and mod100 != 11:
        return f"{n} студент"
    if 2 <= mod10 <= 4 and (mod100 < 10 or mod100 >= 20):
        return f"{n} студента"
    return f"{n} студентов"


def _questions_title(count: int) -> str:
    n = int(count)
    mod10, mod100 = n % 10, n % 100
    if mod10 == 1 and mod100 != 11:
        return f"{n} открытый вопрос"
    if 2 <= mod10 <= 4 and (mod100 < 10 or mod100 >= 20):
        return f"{n} открытых вопроса"
    return f"{n} открытых вопросов"


def _bin_title(count: int) -> str:
    n = int(count)
    mod10, mod100 = n % 10, n % 100
    if mod10 == 1 and mod100 != 11:
        return f"{n} объект в корзине"
    if 2 <= mod10 <= 4 and (mod100 < 10 or mod100 >= 20):
        return f"{n} объекта в корзине"
    return f"{n} объектов в корзине"
