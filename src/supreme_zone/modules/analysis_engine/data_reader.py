from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from ..data_engine.database import MarketDatabase
from ..data_engine.market import MarketBar
from ..data_engine.storage import MarketStorage


@dataclass(slots=True)
class AnalysisDataReader:
    storage: MarketStorage
    database: MarketDatabase

    def load_bars(self, symbol: str, timeframe: str, limit: int = 500) -> tuple[MarketBar, ...]:
        raw = self.storage.load_ohlc(symbol, timeframe)
        if not raw:
            raw = self.database.load_bars(symbol, timeframe, limit=limit)
        bars = tuple(MarketBar.from_mapping(item) for item in raw[-limit:])
        return bars

    def chart_path(self, symbol: str, timeframe: str) -> Path:
        return self.storage.chart_path(symbol, timeframe)

    def available_timeframes(self, symbol: str, preferred: Iterable[str]) -> tuple[str, ...]:
        return tuple(str(frame).upper().strip() for frame in preferred)
