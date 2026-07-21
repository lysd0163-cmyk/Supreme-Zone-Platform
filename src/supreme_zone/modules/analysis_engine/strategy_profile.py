from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..strategy_manager.models import StrategyDefinition
from .models import AnalysisStrategyProfile


@dataclass(slots=True)
class StrategyProfileBuilder:
    def build(self, definition: StrategyDefinition) -> AnalysisStrategyProfile:
        raw = definition.raw if isinstance(definition.raw, dict) else {}
        analysis = raw.get("analysis", {}) if isinstance(raw.get("analysis", {}), dict) else {}
        rules = raw.get("rules", {}) if isinstance(raw.get("rules", {}), dict) else {}

        timeframes = analysis.get("timeframes") or rules.get("timeframes") or ("D1", "H4", "H1", "M15")
        notes: list[str] = []
        for key in ("description", "summary", "notes"):
            value = raw.get(key)
            if isinstance(value, str) and value.strip():
                notes.append(value.strip())
            elif isinstance(value, list):
                notes.extend(str(item).strip() for item in value if str(item).strip())

        return AnalysisStrategyProfile(
            name=definition.name,
            timeframes=tuple(str(item).upper().strip() for item in timeframes if str(item).strip()),
            minimum_candles=int(analysis.get("minimum_candles", rules.get("minimum_candles", 500))),
            lookback_bars=int(analysis.get("lookback_bars", rules.get("lookback_bars", 120))),
            zone_width_ratio=float(analysis.get("zone_width_ratio", rules.get("zone_width_ratio", 0.35))),
            prefer_recent=bool(analysis.get("prefer_recent", rules.get("prefer_recent", True))),
            bias=str(analysis.get("bias", rules.get("bias", "neutral"))).lower(),
            notes=tuple(notes),
        )
