from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from .core.bootstrap import bootstrap
from .core.platform import SupremeZonePlatform


@asynccontextmanager
async def lifespan(app: FastAPI):
    bootstrap_result = bootstrap()
    app.state.bootstrap_result = bootstrap_result
    app.state.platform = bootstrap_result.platform
    yield


app = FastAPI(
    title="Supreme Zone Platform",
    version="0.1.0",
    lifespan=lifespan,
)


def _get_platform() -> SupremeZonePlatform:
    platform = getattr(app.state, "platform", None)
    if not isinstance(platform, SupremeZonePlatform):
        raise HTTPException(status_code=503, detail="Platform is not ready")
    return platform


def _dashboard_html() -> str:
    platform = _get_platform()
    dashboard_service = platform.dashboard_service
    snapshot = dashboard_service.snapshot(
        analysis_engine=platform.analysis_engine,
        search_engine=platform.search_engine,
        monitoring_engine=platform.monitoring_engine,
        execution_engine=platform.execution_engine,
        report_engine=platform.report_engine,
        backtest_engine=platform.backtest_engine,
    )
    html_path = dashboard_service.render(snapshot)
    return html_path.read_text(encoding="utf-8")


@app.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
    return RedirectResponse(url="/dashboard", status_code=307)


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard() -> HTMLResponse:
    return HTMLResponse(content=_dashboard_html())


@app.get("/healthz")
async def healthz() -> dict[str, Any]:
    bootstrap_result = getattr(app.state, "bootstrap_result", None)
    platform = getattr(app.state, "platform", None)
    return {
        "status": "ok",
        "app_name": getattr(bootstrap_result, "app_name", "Supreme Zone Platform"),
        "ready": bool(getattr(bootstrap_result, "ready", False)),
        "platform_ready": isinstance(platform, SupremeZonePlatform),
    }


@app.get("/api/status")
async def api_status() -> dict[str, Any]:
    platform = _get_platform()
    bootstrap_result = getattr(app.state, "bootstrap_result", None)
    snapshot = platform.dashboard_service.snapshot(
        analysis_engine=platform.analysis_engine,
        search_engine=platform.search_engine,
        monitoring_engine=platform.monitoring_engine,
        execution_engine=platform.execution_engine,
        report_engine=platform.report_engine,
        backtest_engine=platform.backtest_engine,
    )
    return {
        "bootstrap": {
            "ready": bool(getattr(bootstrap_result, "ready", False)),
            "app_name": getattr(bootstrap_result, "app_name", "Supreme Zone Platform"),
            "services_registered": list(getattr(bootstrap_result, "services_registered", ())),
        },
        "platform": {
            "cycles": platform.state.cycles,
            "last_error": platform.state.last_error,
            "last_dashboard": str(platform.state.last_dashboard) if platform.state.last_dashboard else None,
        },
        "dashboard": snapshot,
    }


@app.post("/api/run")
async def api_run() -> dict[str, Any]:
    platform = _get_platform()
    result = platform.run_once()
    return {
        "status": "ok",
        "symbols": list(result.symbols),
        "dashboard_path": str(result.dashboard_path) if result.dashboard_path else None,
        "report_count": len(result.report_artifacts),
        "execution_count": len(result.executions),
        "backtest_count": len(result.backtest_results),
    }


@app.get("/api/dashboard")
async def api_dashboard() -> dict[str, Any]:
    platform = _get_platform()
    snapshot = platform.dashboard_service.snapshot(
        analysis_engine=platform.analysis_engine,
        search_engine=platform.search_engine,
        monitoring_engine=platform.monitoring_engine,
        execution_engine=platform.execution_engine,
        report_engine=platform.report_engine,
        backtest_engine=platform.backtest_engine,
    )
    return snapshot
