from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse


_RUNTIME_CONFIG_FILENAME = "data_config.json"


def _coerce_items(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, (list, tuple, set)):
        items = value
    else:
        items = re.split(r"[\n,;،]+", str(value))
    normalized: list[str] = []
    for item in items:
        text = str(item).strip().upper()
        if text and text not in normalized:
            normalized.append(text)
    return tuple(normalized)


def _runtime_config_path(platform) -> Path:
    storage_root = getattr(getattr(platform, "data_engine", None), "storage", None)
    root = getattr(storage_root, "root", Path("storage"))
    return Path(root) / "cache" / _RUNTIME_CONFIG_FILENAME


def _persist_runtime_config(platform, payload: dict[str, Any]) -> None:
    path = _runtime_config_path(platform)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_runtime_config(platform) -> dict[str, Any] | None:
    path = _runtime_config_path(platform)
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return raw if isinstance(raw, dict) else None


def _apply_saved_config(platform, payload: dict[str, Any]) -> None:
    engine = platform.data_engine
    source = str(payload.get("source") or engine.data_source or "mt5").strip().lower() or "mt5"
    symbols = _coerce_items(payload.get("symbols"))
    timeframes = _coerce_items(payload.get("timeframes")) or tuple(engine.timeframe_manager.supported or engine.settings.timeframes)
    bars = payload.get("bars")
    try:
        bars_value = int(bars) if bars not in (None, "") else None
    except Exception:
        bars_value = None
    api_key = payload.get("api_key")
    base_url = payload.get("base_url")
    engine.set_data_source(source, api_key=str(api_key).strip() if api_key not in (None, "") else None, base_url=str(base_url).strip() if base_url not in (None, "") else None)
    if symbols or timeframes:
        from .webapp import _apply_runtime_market_config

        _apply_runtime_market_config(
            symbols or tuple(engine.symbol_manager.symbols or engine.settings.symbols),
            timeframes,
            bars_value,
        )
    engine.status.data_source = engine.data_source
    try:
        from .webapp import app

        app.state.runtime["data_source"] = engine.data_source
        app.state.runtime["bars"] = bars_value
        app.state.runtime["symbols"] = symbols
        app.state.runtime["timeframes"] = timeframes
    except Exception:
        pass


def install_webapp_runtime_fixes() -> None:
    from .webapp import app

    if getattr(app.state, "runtime_fixes_installed", False):
        return
    app.state.runtime_fixes_installed = True

    @app.middleware("http")
    async def _runtime_config_middleware(request: Request, call_next):
        path = request.url.path
        method = request.method.upper()

        try:
            from .webapp import _get_platform

            platform = _get_platform()
        except Exception:
            platform = None

        if platform is not None and path in {"/api/data/config", "/api/data/sync"}:
            saved = _load_runtime_config(platform)
            if saved:
                try:
                    _apply_saved_config(platform, saved)
                except Exception:
                    pass

        if platform is not None and path == "/api/data/config" and method == "POST":
            try:
                payload = await request.json()
            except Exception:
                payload = {}
            if not isinstance(payload, dict):
                payload = {}

            engine = platform.data_engine
            source = str(payload.get("source") or engine.data_source or "mt5").strip().lower() or "mt5"
            symbols = _coerce_items(payload.get("symbols"))
            timeframes = _coerce_items(payload.get("timeframes"))
            bars_raw = payload.get("bars")
            try:
                bars_value = int(bars_raw) if bars_raw not in (None, "") else None
            except Exception:
                bars_value = None
            api_key = payload.get("api_key")
            base_url = payload.get("base_url")

            engine.set_data_source(
                source,
                api_key=str(api_key).strip() if api_key not in (None, "") else None,
                base_url=str(base_url).strip() if base_url not in (None, "") else None,
            )
            if symbols or timeframes:
                from .webapp import _apply_runtime_market_config

                _apply_runtime_market_config(
                    symbols or tuple(engine.symbol_manager.symbols or engine.settings.symbols),
                    timeframes or tuple(engine.timeframe_manager.supported or engine.settings.timeframes),
                    bars_value,
                )
            engine.status.data_source = engine.data_source
            try:
                from .webapp import app as web_app

                web_app.state.runtime["data_source"] = engine.data_source
                web_app.state.runtime["bars"] = bars_value
                web_app.state.runtime["symbols"] = symbols
                web_app.state.runtime["timeframes"] = timeframes
            except Exception:
                pass

            _persist_runtime_config(
                platform,
                {
                    "source": engine.data_source,
                    "symbols": list(symbols or engine.symbol_manager.symbols or engine.settings.symbols),
                    "timeframes": list(timeframes or engine.timeframe_manager.supported or engine.settings.timeframes),
                    "bars": bars_value or engine.settings.market.history_window_candles,
                    "api_key": str(api_key).strip() if api_key not in (None, "") else None,
                    "base_url": str(base_url).strip() if base_url not in (None, "") else engine.twelve_data_base_url,
                },
            )

            from .webapp import _data_config_payload

            return JSONResponse({"ok": True, "data_config": _data_config_payload()})

        if platform is not None and path == "/api/data/sync" and method == "POST":
            engine = platform.data_engine
            if engine.data_source == "twelve_data" and not engine.twelve_data_api_key:
                return JSONResponse({"detail": "Twelve Data API key is missing"}, status_code=400)
            if not engine.symbol_manager.symbols:
                return JSONResponse({"detail": "No symbols configured for data sync"}, status_code=400)

        return await call_next(request)
