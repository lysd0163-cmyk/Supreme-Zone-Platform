from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from ..analysis_engine.models import AnalysisReport, ZoneCandidate
from ..validation_engine.models import ZoneValidationResult


@dataclass(slots=True, frozen=True)
class SearchHit:
    symbol: str
    report: AnalysisReport
    validation: ZoneValidationResult | None
    candidate: ZoneCandidate | None
    discovered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class SearchState:
    total_scanned: int = 0
    total_hits: int = 0
    last_symbol: str | None = None
    last_error: str | None = None
