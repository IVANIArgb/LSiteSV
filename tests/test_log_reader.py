"""Тесты разбора и API логов."""
import pytest
from pathlib import Path

from backend.utils.log_reader import parse_log_lines, query_logs, list_log_files


SAMPLE_LINES = [
    "[INFO]-INFO | 2025-06-01 10:00:00 | backend.app - Server started",
    "[ERROR]-BUG | 2025-06-01 10:01:00 | backend.api - Unexpected state",
    "Traceback (most recent call last):",
    "  File \"api.py\", line 1, in <module>",
    "[WARNING]-WARN | 2025-06-01 10:02:00 | backend.auth - Slow login",
]


class TestLogReader:
    def test_parse_multiline_traceback(self):
        entries = parse_log_lines(SAMPLE_LINES)
        assert len(entries) == 3
        assert "Traceback" in entries[1].message
        assert entries[1].level == "ERROR"
        assert entries[1].category == "BUG"

    def test_query_filters_by_tag(self, tmp_path):
        log_file = tmp_path / "app.log"
        log_file.write_text("\n".join(SAMPLE_LINES), encoding="utf-8")
        result = query_logs(tmp_path, tags=["ERROR-BUG"], sort="time_desc", limit=10)
        assert result["total"] == 1
        assert result["entries"][0]["level"] == "ERROR"
        assert result["entries"][0]["category"] == "BUG"

    def test_query_sort_newest_first(self, tmp_path):
        log_file = tmp_path / "app.log"
        log_file.write_text("\n".join(SAMPLE_LINES), encoding="utf-8")
        result = query_logs(tmp_path, sort="time_desc", limit=10)
        assert result["entries"][0]["level"] == "WARNING"
        assert result["entries"][-1]["level"] == "INFO"

    def test_query_sort_oldest_first(self, tmp_path):
        log_file = tmp_path / "app.log"
        log_file.write_text("\n".join(SAMPLE_LINES), encoding="utf-8")
        result = query_logs(tmp_path, sort="time_asc", limit=10)
        assert result["entries"][0]["level"] == "INFO"
        assert result["entries"][-1]["level"] == "WARNING"

    def test_query_tags_or_within_list(self, tmp_path):
        log_file = tmp_path / "app.log"
        log_file.write_text("\n".join(SAMPLE_LINES), encoding="utf-8")
        result = query_logs(tmp_path, tags=["ERROR-BUG", "WARNING-WARN"], sort="time_desc", limit=10)
        assert result["total"] == 2
        assert {f"{e['level']}-{e['category']}" for e in result["entries"]} == {"ERROR-BUG", "WARNING-WARN"}

    def test_list_log_files(self, tmp_path):
        (tmp_path / "app.log").write_text("", encoding="utf-8")
        (tmp_path / "app.log.1").write_text("", encoding="utf-8")
        (tmp_path / "evil.log").write_text("", encoding="utf-8")
        names = list_log_files(tmp_path)
        assert "app.log" in names
        assert "app.log.1" in names
        assert "evil.log" not in names


class TestAdminLogsApi:
    def test_user_forbidden(self, client, mock_kerberos_and_ad, sample_user):
        resp = client.get(
            "/api/admin/logs",
            headers={"Authorization": "Negotiate FAKE_TOKEN_USER"},
        )
        assert resp.status_code == 403

    def test_admin_can_read_logs(self, app, client, mock_kerberos_and_ad, sample_admin, tmp_path):
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        (log_dir / "app.log").write_text(
            "[INFO]-INFO | 2025-06-01 12:00:00 | test - hello\n",
            encoding="utf-8",
        )
        app.config["LOG_DIR"] = str(log_dir)

        resp = client.get(
            "/api/admin/logs",
            headers={"Authorization": "Negotiate FAKE_TOKEN_ADMIN"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total"] >= 1
        assert data["entries"][0]["message"] == "hello"

    def test_logs_page_admin(self, client, mock_kerberos_and_ad, sample_admin):
        resp = client.get(
            "/logs",
            headers={"Authorization": "Negotiate FAKE_TOKEN_ADMIN"},
        )
        assert resp.status_code == 200
        assert b"logs-console" in resp.data
