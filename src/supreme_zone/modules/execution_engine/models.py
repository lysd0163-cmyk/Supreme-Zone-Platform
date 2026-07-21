from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from ..entry_engine.models import EntrySignal


class TradeSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class ExecutionStatus(str, Enum):
    PENDING = "PENDING"
    SENT = "SENT"
    FILLED = "FILLED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


@dataclass(slots=True, frozen=True)
class TradeRequest:
    symbol: str
    side: TradeSide
    volume: float
    stop_loss: float | None = None
    take_profit: float | None = None
    comment: str = "supreme-zone-platform"
    magic: int = 0
    source_signal: EntrySignal | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class TradeResult:
    request: TradeRequest
    status: ExecutionStatus
    broker_response: dict[str, Any] | None = None
    error: str | None = None
