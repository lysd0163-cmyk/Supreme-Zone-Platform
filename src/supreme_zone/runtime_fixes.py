from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .modules.data_engine.service import DataEngine
from .modules.data_engine.symbol_manager import SymbolManager
from .modules.data_engine.timeframe_manager import TimeframeManager
from .modules.strategy_manager.service import StrategyManager


_RUNTIME_CONFIG_FILENAME = "data_config.json"
_STRATEGY_STATE_FILENAME = "strategy_state.json"
_PATCHED = False
_LAST_RUNTIME_CONFIG: dict[str, Any] = {}
_LAST_STRATEGY_STATE: dict[str, Any] = {}


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


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return raw if isinstance(raw, dict) else None


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def save_runtime_config(platform, payload: dict[str, Any]) -> None:
    global _LAST_RUNTIME_CONFIG
    _LAST_RUNTIME_CONFIG = {**_LAST_RUNTIME_CONFIG, **payload}
    if platform is not None:
        _write_json(_runtime_config_path(platform), _LAST_RUNTIME_CONFIG)


def load_runtime_config(platform) -> dict[str, Any] | None:
    loaded = _read_json(_runtime_config_path(platform))
    if loaded is not None:
        global _LAST_RUNTIME_CONFIG
        _LAST_RUNTIME_CONFIG = dict(loaded)
    return loaded


def save_strategy_state(platform, payload: dict[str, Any]) -> None:
    global _LAST_STRATEGY_STATE
    _LAST_STRATEGY_STATE = {**_LAST_STRATEGY_STATE, **payload}
    if platform is not None:
        _write_json(_strategy_state_path(platform), _LAST_STRATEGY_STATE)


def load_strategy_state(platform) -> dict[str, Any] | None:
    loaded = _read_json(_strategy_state_path(platform))
    if loaded is not None:
        global _LAST_STRATEGY_STATE
        _LAST_STRATEGY_STATE = dict(loaded)
    return loaded


def install_runtime_persistence_patches(platform=None) -> None:
    global _PATCHED
    if _PATCHED:
        return

    if platform is not None:
        load_runtime_config(platform)
        load_strategy_state(platform)

    original_set_data_source = DataEngine.set_data_source
    original_symbol_load = SymbolManager.load
    original_timeframe_load = TimeframeManager.load
    original_add_strategy_file = StrategyManager.add_strategy_file
    original_activate_strategy = StrategyManager.activate_strategy
    original_deactivate_strategy = StrategyManager.deactivate_strategy

    def set_data_source(self: DataEngine, source: str, api_key: str | None = None, base_url: str | None = None) -> None:
        original_set_data_source(self, source, api_key=api_key, base_url=base_url)
        save_runtime_config(
            platform,
            {
                "source": self.data_source,
                "api_key": self.twelve_data_api_key,
                "base_url": self.twelve_data_base_url,
                "symbols": list(self.symbol_manager.symbols or self.settings.symbols),
                "timeframes": list(self.timeframe_manager.supported or self.settings.timeframes),
                "bars": int(getattr(self.settings.market, "history_window_candles", 500) or 500),
            },
        )

    def symbol_load(self: SymbolManager, symbols: list[str] | tuple[str, ...] | None) -> None:
        original_symbol_load(self, symbols)
        save_runtime_config(
            platform,
            {
                "symbols": list(self.symbols),
            },
        )

    def timeframe_load(self: TimeframeManager, timeframes: list[str] | tuple[str, ...] | None) -> None:
        original_timeframe_load(self, timeframes)
        save_runtime_config(
            platform,
            {
                "timeframes": list(self.supported),
            },
        )

    def add_strategy_file(self: StrategyManager, path: str | Path):
        strategy = original_add_strategy_file(self, path)
        save_strategy_state(
            platform,
            {
                "strategy_path": str(strategy.source_path),
                "strategy_name": strategy.name,
                "strategy_version": strategy.version,
                "active": bool(strategy.active),
            },
        )
        return strategy

    def activate_strategy(self: StrategyManager, name: str):
        strategy = original_activate_strategy(self, name)
        save_strategy_state(
            platform,
            {
                "strategy_path": str(strategy.source_path),
                "strategy_name": strategy.name,
                "strategy_version": strategy.version,
                "active": True,
            },
        )
        return strategy

    def deactivate_strategy(self: StrategyManager) -> None:
        original_deactivate_strategy(self)
        save_strategy_state(platform, {**_LAST_STRATEGY_STATE, "active": False})

    DataEngine.set_data_source = set_data_source  # type: ignore[assignment]
    SymbolManager.load = symbol_load  # type: ignore[assignment]
    TimeframeManager.load = timeframe_load  # type: ignore[assignment]
    StrategyManager.add_strategy_file = add_strategy_file  # type: ignore[assignment]
    StrategyManager.activate_strategy = activate_strategy  # type: ignore[assignment]
    StrategyManager.deactivate_strategy = deactivate_strategy  # type: ignore[assignment]
    _PATCHED = True


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
