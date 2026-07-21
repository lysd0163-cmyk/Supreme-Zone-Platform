from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True, frozen=True)
class MT5Credentials:
    server: str
    login: int
    password: str


@dataclass(slots=True, frozen=True)
class MarketDataRequest:
    symbol: str
    timeframe: str
    bars: int = 500


@dataclass(slots=True, frozen=True)
class ChartRequest:
    symbol: str
    timeframe: str
    output_path: Path
