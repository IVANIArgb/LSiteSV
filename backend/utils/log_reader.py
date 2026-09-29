"""
Чтение и разбор файлов логов приложения ([LEVEL]-CATEGORY | timestamp | logger - message).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# [ERROR]-BUG | 2025-02-01 12:00:00,123 | backend.api - message
LOG_LINE_RE = re.compile(
    r"^\[(?P<level>[A-Z]+)\]-(?P<category>[A-Z]+) \| (?P<timestamp>.+?) \| (?P<logger>[^ ]+) - (?P<message>.*)$"
)

ALLOWED_LOG_BASENAME = re.compile(r"^app\.log(\.\d+)?$")

LEVEL_ORDER = {
    "CRITICAL": 0,
    "ERROR": 1,
    "WARNING": 2,
    "WARN": 2,
    "INFO": 3,
    "DEBUG": 4,
}

CATEGORY_ORDER = {
    "CRITICAL": 0,
    "ERROR": 1,
    "BUG": 2,
    "WARN": 3,
    "ATTEMPT": 4,
    "INFO": 5,
}


@dataclass
class LogEntry:
    level: str
    category: str
    timestamp: str
    logger: str
    message: str
    raw: str
    line_no: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _parse_timestamp(value: str) -> datetime:
    for fmt in ("%Y-%m-%d %H:%M:%S,%f", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(value.strip(), fmt)
        except ValueError:
            continue
    return datetime.min


def _is_allowed_log_file(log_dir: Path, filename: str) -> bool:
    if not ALLOWED_LOG_BASENAME.match(filename or ""):
        return False
    candidate = (log_dir / filename).resolve()
    try:
        candidate.relative_to(log_dir.resolve())
    except ValueError:
        return False
    return True


def list_log_files(log_dir: Path) -> List[str]:
    """Список доступных файлов логов (app.log, app.log.1, …)."""
    if not log_dir.is_dir():
        return []
    names = [p.name for p in log_dir.iterdir() if p.is_file() and ALLOWED_LOG_BASENAME.match(p.name)]
    names.sort(key=lambda n: (0 if n == "app.log" else 1, n))
    return names


def parse_log_lines(lines: List[str], start_line_no: int = 1) -> List[LogEntry]:
    """Разобрать строки файла в записи (многострочные traceback — к предыдущей записи)."""
    entries: List[LogEntry] = []
    current: Optional[LogEntry] = None

    for offset, line in enumerate(lines):
        line_no = start_line_no + offset
        stripped = line.rstrip("\n\r")
        match = LOG_LINE_RE.match(stripped)
        if match:
            current = LogEntry(
                level=match.group("level"),
                category=match.group("category"),
                timestamp=match.group("timestamp"),
                logger=match.group("logger"),
                message=match.group("message"),
                raw=stripped,
                line_no=line_no,
            )
            entries.append(current)
            continue
        if current is not None and stripped:
            current.message = f"{current.message}\n{stripped}"
            current.raw = f"{current.raw}\n{stripped}"

    return entries


def read_log_file(log_dir: Path, filename: str = "app.log") -> List[LogEntry]:
    if not _is_allowed_log_file(log_dir, filename):
        return []
    path = log_dir / filename
    if not path.is_file():
        return []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    return parse_log_lines(text.splitlines())


def _count_by(entries: List[LogEntry], key: str) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for entry in entries:
        value = getattr(entry, key, "") or "UNKNOWN"
        counts[value] = counts.get(value, 0) + 1
    return counts


def entry_tag_key(entry: LogEntry) -> str:
    """Ключ метки записи: ERROR-BUG (уровень-категория)."""
    return f"{entry.level}-{entry.category}"


def _count_by_tag(entries: List[LogEntry]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for entry in entries:
        key = entry_tag_key(entry)
        counts[key] = counts.get(key, 0) + 1
    return counts


def _normalize_tag(value: str) -> Optional[str]:
    raw = (value or "").strip().upper().replace("[", "").replace("]", "")
    if "-" not in raw:
        return None
    level, category = raw.split("-", 1)
    level = level.strip()
    category = category.strip()
    if level and category:
        return f"{level}-{category}"
    return None


def _normalize_tag_list(values: Optional[List[str]]) -> List[str]:
    if not values:
        return []
    result: List[str] = []
    for value in values:
        for part in str(value).split(","):
            tag = _normalize_tag(part)
            if tag and tag not in result:
                result.append(tag)
    return result


def _sort_entries(entries: List[LogEntry], sort: str) -> List[LogEntry]:
    sort_key = (sort or "time_desc").strip().lower()
    if sort_key == "file":
        return sorted(entries, key=lambda e: e.line_no)
    if sort_key == "time_asc":
        return sorted(entries, key=lambda e: (_parse_timestamp(e.timestamp), e.line_no))
    if sort_key == "time_desc":
        return sorted(entries, key=lambda e: (_parse_timestamp(e.timestamp), e.line_no), reverse=True)
    if sort_key == "level":
        return sorted(
            entries,
            key=lambda e: (LEVEL_ORDER.get(e.level, 99), _parse_timestamp(e.timestamp), e.line_no),
        )
    if sort_key == "level_desc":
        return sorted(
            entries,
            key=lambda e: (LEVEL_ORDER.get(e.level, 99), _parse_timestamp(e.timestamp), e.line_no),
            reverse=True,
        )
    if sort_key == "category":
        return sorted(
            entries,
            key=lambda e: (CATEGORY_ORDER.get(e.category, 99), _parse_timestamp(e.timestamp), e.line_no),
        )
    if sort_key == "category_desc":
        return sorted(
            entries,
            key=lambda e: (CATEGORY_ORDER.get(e.category, 99), _parse_timestamp(e.timestamp), e.line_no),
            reverse=True,
        )
    if sort_key == "logger":
        return sorted(entries, key=lambda e: (e.logger.lower(), _parse_timestamp(e.timestamp), e.line_no))
    return sorted(entries, key=lambda e: (_parse_timestamp(e.timestamp), e.line_no), reverse=True)


def _normalize_filter_list(values: Optional[List[str]]) -> List[str]:
    if not values:
        return []
    result: List[str] = []
    for value in values:
        for part in str(value).split(","):
            item = part.strip().upper()
            if item and item not in result:
                result.append(item)
    return result


def query_logs(
    log_dir: Path,
    *,
    filename: str = "app.log",
    level: Optional[str] = None,
    category: Optional[str] = None,
    levels: Optional[List[str]] = None,
    categories: Optional[List[str]] = None,
    tags: Optional[List[str]] = None,
    search: Optional[str] = None,
    sort: str = "time_desc",
    limit: int = 500,
    offset: int = 0,
) -> Dict[str, Any]:
    """Прочитать логи с фильтрами, сортировкой и пагинацией.

    tags — метки вида ERROR-BUG ([LEVEL]-CATEGORY), OR внутри списка.
    levels/categories — устаревший способ, оставлен для совместимости.
    """
    files = list_log_files(log_dir)
    if filename and filename not in files:
        if not _is_allowed_log_file(log_dir, filename):
            filename = "app.log"
        elif not (log_dir / filename).is_file():
            filename = files[0] if files else "app.log"
    elif not filename:
        filename = files[0] if files else "app.log"

    all_entries = read_log_file(log_dir, filename)
    level_filters = _normalize_filter_list(levels)
    category_filters = _normalize_filter_list(categories)
    if not level_filters and level:
        level_filters = _normalize_filter_list([level])
    if not category_filters and category:
        category_filters = _normalize_filter_list([category])
    tag_filters = _normalize_tag_list(tags)
    search_filter = (search or "").strip().lower()

    filtered: List[LogEntry] = []
    for entry in all_entries:
        if tag_filters and entry_tag_key(entry) not in tag_filters:
            continue
        if level_filters and entry.level not in level_filters:
            continue
        if category_filters and entry.category not in category_filters:
            continue
        if search_filter:
            haystack = f"{entry.message} {entry.logger} {entry.raw}".lower()
            if search_filter not in haystack:
                continue
        filtered.append(entry)

    sorted_entries = _sort_entries(filtered, sort)
    total = len(sorted_entries)
    safe_limit = max(1, min(int(limit or 500), 2000))
    safe_offset = max(0, int(offset or 0))
    page = sorted_entries[safe_offset : safe_offset + safe_limit]

    return {
        "files": files,
        "file": filename,
        "total": total,
        "offset": safe_offset,
        "limit": safe_limit,
        "entries": [e.to_dict() for e in page],
        "stats": {
            "by_tag": _count_by_tag(all_entries),
            "filtered_total": total,
        },
    }
