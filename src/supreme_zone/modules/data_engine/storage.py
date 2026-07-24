from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .market import MarketBar


_SYMBOL_FILE_SAFE = re.compile(r"[^A-Z0-9]+")


@dataclass(slots=True)
class MarketStorage:
    root: Path = Path("storage")
    charts_dir: Path = Path("storage/charts")
    ohlc_dir: Path = Path("storage/ohlc")

    def ensure(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.charts_dir.mkdir(parents=True, exist_ok=True)
        self.ohlc_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _safe_part(value: str) -> str:
        text = str(value or "").upper().strip().replace(" ", "")
        text = text.replace("/", "_")
        text = _SYMBOL_FILE_SAFE.sub("_", text)
        text = re.sub(r"_+", "_", text).strip("_")
        return text or "UNKNOWN"

    def ohlc_path(self, symbol: str, timeframe: str) -> Path:
        return self.ohlc_dir / f"{self._safe_part(symbol)}_{self._safe_part(timeframe)}.json"

    def chart_path(self, symbol: str, timeframe: str) -> Path:
        return self.charts_dir / f"{self._safe_part(symbol)}_{self._safe_part(timeframe)}.png"

    def save_ohlc(self, symbol: str, timeframe: str, bars: list[MarketBar]) -> Path:
        self.ensure()
        path = self.ohlc_path(symbol, timeframe)
        path.parent.mkdir(parents=True, exist_ok=True)
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