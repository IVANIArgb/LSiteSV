"""Маршруты Flask: страницы сайта и admin API."""

from backend.routes.admin_routes import admin_routes_bp, register_admin_routes
from backend.routes.pages import register_routes

__all__ = ["admin_routes_bp", "register_admin_routes", "register_routes"]
