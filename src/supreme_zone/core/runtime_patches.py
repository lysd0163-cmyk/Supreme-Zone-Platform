from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from threading import RLock
from typing import Any

from ..modules.analysis_engine.service import AnalysisEngine
from ..modules.data_engine.service import DataEngine
from ..modules.data_engine.symbol_manager import SymbolManager
from ..modules.data_engine.timeframe_manager import TimeframeManager

_STATE_DIR = Path("storage/cache")
_SYMBOLS_FILE = _STATE_DIR / "symbols.json"
_TIMEFRAMES_FILE = _STATE_DIR / "timeframes.json"
_DATA_SOURCE_FILE = _STATE_DIR / "data_source.json"
_LOCK = RLock()
_PATCHED = False
_RESTORING = False


def _ensure_state_dir() -> None:
    _STATE_DIR.mkdir(parents=True, exist_ok=True)


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: Path, payload: Any) -> None:
    _ensure_state_dir()
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _restore_persisted_state(engine: DataEngine) -> None:
    symbols = _read_json(_SYMBOLS_FILE, None)
    if isinstance(symbols, list) and symbols:
        engine.symbol_manager.load(symbols)

    timeframes = _read_json(_TIMEFRAMES_FILE, None)
    if isinstance(timeframes, list) and timeframes:
        engine.timeframe_manager.load(timeframes)

    data_source = _read_json(_DATA_SOURCE_FILE, None)
    if isinstance(data_source, dict) and data_source:
        source = str(data_source.get("source", engine.data_source or "mt5")).strip().lower() or "mt5"
        api_key = data_source.get("api_key")
        base_url = data_source.get("base_url")
        engine.set_data_source(
            source,
            api_key=str(api_key) if api_key not in (None, "") else None,
            base_url=str(base_url) if base_url not in (None, "") else None,
        )

    if isinstance(engine.settings, object) and hasattr(engine.settings, "market"):
        try:
            engine.settings = replace(
                engine.settings,
                market=replace(
                    engine.settings.market,
                    symbols=tuple(engine.symbol_manager.symbols),
                    timeframes=tuple(engine.timeframe_manager.supported),
                ),
            )
        except Exception:
            pass


def _patch_symbol_manager() -> None:
    original_load = SymbolManager.load

    def load(self: SymbolManager, symbols: list[str] | tuple[str, ...] | None) -> None:
        original_load(self, symbols)
        if not _RESTORING:
            _write_json(_SYMBOLS_FILE, list(self.symbols))

    SymbolManager.load = load  # type: ignore[assignment]


def _patch_timeframe_manager() -> None:
    original_load = TimeframeManager.load

    def load(self: TimeframeManager, timeframes: list[str] | tuple[str, ...] | None) -> None:
        original_load(self, timeframes)
        if not _RESTORING:
            _write_json(_TIMEFRAMES_FILE, list(self.supported))

    TimeframeManager.load = load  # type: ignore[assignment]


def _patch_data_engine() -> None:
    original_init = DataEngine.__init__
    original_set_data_source = DataEngine.set_data_source

    def __init__(self: DataEngine, *args: Any, **kwargs: Any) -> None:
        global _RESTORING
        _RESTORING = True
        try:
            original_init(self, *args, **kwargs)
        finally:
            _RESTORING = False
        _restore_persisted_state(self)

    def set_data_source(self: DataEngine, source: str, api_key: str | None = None, base_url: str | None = None) -> None:
        original_set_data_source(self, source, api_key=api_key, base_url=base_url)
        if not _RESTORING:
            _write_json(
                _DATA_SOURCE_FILE,
                {
                    "source": self.data_source,
                    "api_key": self.twelve_data_api_key,
                    "base_url": self.twelve_data_base_url,
                },
            )

    DataEngine.__init__ = __init__  # type: ignore[assignment]
    DataEngine.set_data_source = set_data_source  # type: ignore[assignment]


def _patch_analysis_engine() -> None:
    original_init = AnalysisEngine.__init__

    def __init__(self: AnalysisEngine, settings: Any, data_engine: DataEngine, *args: Any, **kwargs: Any) -> None:
        original_init(self, settings, data_engine, *args, **kwargs)
        try:
            self.settings = data_engine.settings
        except Exception:
            pass

    AnalysisEngine.__init__ = __init__  # type: ignore[assignment]


def install_runtime_patches() -> None:
    global _PATCHED
    with _LOCK:
        if _PATCHED:
            return
        _patch_symbol_manager()
        _patch_timeframe_manager()
        _patch_data_engine()
        _patch_analysis_engine()
        _PATCHED = True
