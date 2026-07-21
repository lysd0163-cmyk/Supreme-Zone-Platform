from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..analysis_engine.models import AnalysisReport
from ..entry_engine.models import EntrySignal
from ..execution_engine.models import TradeResult
from ..validation_engine.models import ZoneValidationResult


@dataclass(slots=True, frozen=True)
class ReportBundle:
    symbol: str
    analysis: AnalysisReport
    validation: dict[str, ZoneValidationResult] = field(default_factory=dict)
    entry: EntrySignal | None = None
    execution: TradeResult | None = None
    backtest: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(slots=True, frozen=True)
class ReportArtifact:
    json_path: Path
    markdown_path: Path
    summary_path: Path | None = None
