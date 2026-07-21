from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from ..analysis_engine.models import ZoneCandidate, ZoneSide
from ..validation_engine.models import ZoneValidationResult


class EntryStatus(str, Enum):
    WAITING = "WAITING"
    BREAK_CONFIRMED = "BREAK_CONFIRMED"
    RETEST_CONFIRMED = "RETEST_CONFIRMED"
    CONFIRMED = "CONFIRMED"
    INVALID = "INVALID"


@dataclass(slots=True, frozen=True)
class EntrySignal:
    symbol: str
    timeframe: str
    side: ZoneSide
    status: EntryStatus
    entry_price: float | None
    stop_loss: float | None
    take_profit: float | None
    candidate: ZoneCandidate
    validation: ZoneValidationResult | None = None
    evidence: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
