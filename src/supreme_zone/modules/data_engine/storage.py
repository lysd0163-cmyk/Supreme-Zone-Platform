from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .market import MarketBar


@dataclass(slots=True)
class MarketStorage:
    root: Path = Path("storage")
    charts_dir: Path = Path("storage/charts")
    ohlc_dir: Path = Path("storage/ohlc")

    def ensure(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.charts_dir.mkdir(parents=True, exist_ok=True)
        self.ohlc_dir.mkdir(parents=True, exist_ok=True)

    def ohlc_path(self, symbol: str, timeframe: str) -> Path:
        return self.ohlc_dir / f"{symbol.upper()}_{timeframe.upper()}.json"

    def chart_path(self, symbol: str, timeframe: str) -> Path:
        return self.charts_dir / f"{symbol.upper()}_{timeframe.upper()}.png"

    def save_ohlc(self, symbol: str, timeframe: str, bars: list[MarketBar]) -> Path:
        self.ensure()
        path = self.ohlc_path(symbol, timeframe)
        path.write_text(
            json.dumps([bar.to_mapping() for bar in bars], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return path

    def load_ohlc(self, symbol: str, timeframe: str) -> list[dict[str, Any]]:
        path = self.ohlc_path(symbol, timeframe)
        if not path.exists():
            return []
        raw = json.loads(path.read_text(encoding="utf-8"))
        return [dict(item) for item in raw]
