from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from ..analysis_engine.models import AnalysisReport, ZoneCandidate
from ..entry_engine.models import EntrySignal
from ..validation_engine.models import ZoneValidationResult


@dataclass(slots=True, frozen=True)
class MonitoredZone:
    symbol: str
    candidate: ZoneCandidate
    validation: ZoneValidationResult | None = None
    entry: EntrySignal | None = None
    report: AnalysisReport | None = None
    last_checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class MonitoringState:
    running: bool = False
    cycles: int = 0
    invalidations: int = 0
    reanalyses: int = 0
    last_error: str | None = None
