from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


_RUNTIME_CONFIG_FILENAME = "data_config.json"
_STRATEGY_STATE_FILENAME = "strategy_state.json"


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


def _storage_root(platform) -> Path:
    storage_root = getattr(getattr(platform, "data_engine", None), "storage", None)
    root = getattr(storage_root, "root", Path("storage"))
    return Path(root)


def _runtime_config_path(platform) -> Path:
    return _storage_root(platform) / "cache" / _RUNTIME_CONFIG_FILENAME


def _strategy_state_path(platform) -> Path:
    return _storage_root(platform) / "cache" / _STRATEGY_STATE_FILENAME


def save_runtime_config(platform, payload: dict[str, Any]) -> None:
    path = _runtime_config_path(platform)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_runtime_config(platform) -> dict[str, Any] | None:
    path = _runtime_config_path(platform)
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return raw if isinstance(raw, dict) else None


def save_strategy_state(platform, payload: dict[str, Any]) -> None:
    path = _strategy_state_path(platform)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_strategy_state(platform) -> dict[str, Any] | None:
    path = _strategy_state_path(platform)
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return raw if isinstance(raw, dict) else None


def apply_runtime_config(platform, payload: dict[str, Any]) -> None:
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

    engine.set_data_source(
        source,
        api_key=str(api_key).strip() if api_key not in (None, "") else None,
        base_url=str(base_url).strip() if base_url not in (None, "") else None,
    )
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


def restore_persisted_state(platform) -> None:
    saved_config = load_runtime_config(platform)
    if saved_config:
        try:
            apply_runtime_config(platform, saved_config)
        except Exception:
            pass

    saved_strategy = load_strategy_state(platform)
    if not saved_strategy:
        return

    strategy_path = saved_strategy.get("strategy_path")
    if not strategy_path:
        return

    path = Path(str(strategy_path))
    if not path.exists():
        return

    manager = platform.analysis_engine.strategy_manager
    try:
        strategy = manager.add_strategy_file(path)
        if bool(saved_strategy.get("active", True)):
            manager.activate_strategy(strategy.name)
        try:
            from .webapp import app

            app.state.runtime["strategy_path"] = str(path)
        except Exception:
            pass
    except Exception:
        return
