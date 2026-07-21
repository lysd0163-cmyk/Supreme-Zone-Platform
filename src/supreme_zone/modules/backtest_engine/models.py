from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(slots=True, frozen=True)
class BacktestResult:
    symbol: str
    strategy_name: str
    trades: int
    wins: int
    losses: int
    win_rate: float
    profit_factor: float
    start: datetime | None = None
    end: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class BacktestState:
    runs: int = 0
    last_symbol: str | None = None
    last_error: str | None = None
