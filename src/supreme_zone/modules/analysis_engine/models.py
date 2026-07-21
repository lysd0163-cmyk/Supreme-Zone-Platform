from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from ..data_engine.market import MarketBar


class ZoneSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


@dataclass(slots=True, frozen=True)
class ChartImageSnapshot:
    path: Path
    width: int
    height: int
    file_size: int
    aspect_ratio: float
    brightness: float
    contrast: float
    digest: str


@dataclass(slots=True, frozen=True)
class AnalysisStrategyProfile:
    name: str
    timeframes: tuple[str, ...] = ("D1", "H4", "H1", "M15")
    minimum_candles: int = 500
    lookback_bars: int = 120
    zone_width_ratio: float = 0.35
    prefer_recent: bool = True
    bias: str = "neutral"
    notes: tuple[str, ...] = ()


@dataclass(slots=True, frozen=True)
class ZoneCandidate:
    side: ZoneSide
    timeframe: str
    symbol: str
    lower: float
    upper: float
    score: float
    source: str
    evidence: tuple[str, ...] = ()

    @property
    def midpoint(self) -> float:
        return (self.lower + self.upper) / 2.0

    @property
    def width(self) -> float:
        return abs(self.upper - self.lower)


@dataclass(slots=True, frozen=True)
class FrameAnalysis:
    symbol: str
    timeframe: str
    bars: tuple[MarketBar, ...]
    image: ChartImageSnapshot | None
    trend: str
    volatility: float
    buy_candidate: ZoneCandidate | None
    sell_candidate: ZoneCandidate | None
    swing_highs: tuple[float, ...] = ()
    swing_lows: tuple[float, ...] = ()
    notes: tuple[str, ...] = ()


@dataclass(slots=True, frozen=True)
class AnalysisReport:
    symbol: str
    strategy_name: str
    frame_analyses: tuple[FrameAnalysis, ...]
    buy_zone: ZoneCandidate | None
    sell_zone: ZoneCandidate | None
    created_from: str = "analysis-engine"
    metadata: dict[str, Any] = field(default_factory=dict)
