"""Тесты сборки данных админ-дашборда."""
from datetime import datetime, timedelta

import pytest

from backend.utils.admin_dashboard import _news_href, build_admin_dashboard
from database.models import Category, Course, NewsEvent, Question, User, UserCourseProgress


class TestAdminDashboardHelpers:
    def test_news_href_course(self):
        assert _news_href("course_created", {"course_id": 3, "category_id": 1}) == "/all-courses-pg?category_id=1"

    def test_news_href_lesson(self):
        assert _news_href("lesson_created", {"lesson_id": 5, "course_id": 2}) == "/lessons-content-pg?lesson_id=5"


class TestBuildAdminDashboard:
    def test_empty_db_returns_structure(self, app, db_session):
        with app.app_context():
            data = build_admin_dashboard(db_session, active_limit=5, news_limit=3, stats_limit=5)
        assert "active_courses" in data
        assert "notifications" in data
        assert "course_stats" in data
        assert isinstance(data["active_courses"], list)

    def test_course_stats_with_enrollment(self, app, db_session):
        cat = Category(title="Test Cat", description="")
        user = User(username="dash_user", department="IT", role="user")
        db_session.add(cat)
        db_session.flush()
        course = Course(category_id=cat.id, title="Dash Course", total_lessons=2, is_active=True)
        db_session.add_all([user, course])
        db_session.flush()
        db_session.add(
            UserCourseProgress(user_id=user.id, course_id=course.id, lessons_completed=1, is_completed=False)
        )
        db_session.commit()

        with app.app_context():
            data = build_admin_dashboard(db_session, stats_limit=10)

        stat = next((c for c in data["course_stats"] if c["id"] == course.id), None)
        assert stat is not None
        assert stat["students_count"] == 1

    def test_notifications_include_open_questions(self, app, db_session):
        author = User(username="qauthor", department="IT", role="user")
        db_session.add(author)
        db_session.flush()
        db_session.add(
            Question(author_id=author.id, title="Open?", body="Help", is_resolved=False)
        )
        db_session.commit()

        with app.app_context():
            data = build_admin_dashboard(db_session)

        titles = [n["title"] for n in data["notifications"]]
        assert any("открыт" in t.lower() for t in titles)

    def test_notifications_include_recent_news(self, app, db_session):
        author = User(username="newsauthor", department="IT", role="admin")
        db_session.add(author)
        db_session.flush()
        db_session.add(
            NewsEvent(
                event_type="manual",
                title="Тестовое событие",
                body=None,
                meta='{"course_id": 1}',
                created_by=author.id,
            )
        )
        db_session.commit()

        with app.app_context():
            data = build_admin_dashboard(db_session)

        assert any(n.get("title") == "Тестовое событие" for n in data["notifications"])
