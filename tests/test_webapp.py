from __future__ import annotations

from supreme_zone.webapp import app


def test_webapp_is_fastapi_app() -> None:
    assert app.title == "Supreme Zone Platform"
    routes = {route.path for route in app.routes}
    assert "/dashboard" in routes
    assert "/api/status" in routes
    assert "/api/run" in routes
    assert "/healthz" in routes
