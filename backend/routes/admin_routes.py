"""
Административные эндпоинты: валидация структуры контента, hot reload.
"""

from __future__ import annotations

from flask import Blueprint, jsonify, g, request

from backend.content_validator import (
    validate_and_fix_structure,
    reload_content,
    get_content_cache_version,
    maybe_git_commit,
)

admin_routes_bp = Blueprint("admin_routes", __name__, url_prefix="/api/admin")


def _require_admin(user_info) -> tuple | None:
    """Проверка прав admin/super_admin (упрощённая копия логики api.py)."""
    if not user_info:
        return jsonify({"error": "Unauthorized"}), 401
    username = (user_info.get("username") or "").strip().lower()
    if not username or username in {"guest", "user"}:
        return jsonify({"error": "Unauthorized"}), 401
    if (user_info.get("auth_method") or "").strip().lower() in {"none", ""}:
        return jsonify({"error": "Unauthorized"}), 401
    role = (user_info.get("role") or "user").strip().lower()
    if role not in ("admin", "super_admin"):
        return jsonify({"error": "Forbidden"}), 403
    return None


@admin_routes_bp.route("/validate-structure", methods=["GET", "POST"])
def admin_validate_structure():
    """
    Ручной запуск валидации и автоисправления структуры контента.

    GET  — только проверка (fix=false).
    POST — проверка + исправление (fix=true по умолчанию).
    JSON POST: {"fix": true, "git_commit": false}
    """
    deny = _require_admin(g.get("user_info"))
    if deny:
        return deny

    fix = True
    git_commit = False
    if request.method == "GET":
        fix = request.args.get("fix", "false").lower() in ("1", "true", "yes")
    else:
        data = request.get_json(silent=True) or {}
        if "fix" in data:
            fix = bool(data.get("fix"))
        git_commit = bool(data.get("git_commit"))

    report = validate_and_fix_structure(fix=fix)
    result = report.to_dict()
    result["cache_version"] = get_content_cache_version()

    if fix and git_commit:
        commit_hash = maybe_git_commit("LMS: auto-fix content structure")
        result["git_commit"] = commit_hash

    return jsonify(result)


@admin_routes_bp.route("/reload-content", methods=["POST"])
def admin_reload_content():
    """
    Горячая перезагрузка контента без перезапуска сервера.
    Выполняет validate+fix и увеличивает версию кэша.
    """
    deny = _require_admin(g.get("user_info"))
    if deny:
        return deny

    data = request.get_json(silent=True) or {}
    git_commit = bool(data.get("git_commit"))
    payload = reload_content()
    if git_commit:
        payload["git_commit"] = maybe_git_commit("LMS: content reload")
    return jsonify(payload)


@admin_routes_bp.route("/content-cache-version", methods=["GET"])
def admin_content_cache_version():
    """Текущая версия кэша контента (для отладки hot reload)."""
    deny = _require_admin(g.get("user_info"))
    if deny:
        return deny
    return jsonify({"cache_version": get_content_cache_version()})


def register_admin_routes(app, csrf=None) -> Blueprint:
    """Зарегистрировать admin routes в приложении."""
    app.register_blueprint(admin_routes_bp)
    if csrf is not None:
        csrf.exempt(admin_routes_bp)
    return admin_routes_bp
