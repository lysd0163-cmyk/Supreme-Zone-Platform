from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..strategy_manager.models import StrategyDefinition
from .models import AnalysisStrategyProfile


@dataclass(slots=True)
class StrategyProfileBuilder:
    def build(self, definition: StrategyDefinition) -> AnalysisStrategyProfile:
        raw = definition.raw if isinstance(definition.raw, dict) else {}
        interpretation = definition.interpretation if isinstance(definition.interpretation, dict) else {}
        interpreter = interpretation if isinstance(interpretation, dict) else {}

        analysis = self._merge_mapping(
            raw.get("analysis") if isinstance(raw.get("analysis"), dict) else {},
            interpreter.get("analysis") if isinstance(interpreter.get("analysis"), dict) else {},
        )
        rules = self._merge_mapping(
            raw.get("rules") if isinstance(raw.get("rules"), dict) else {},
            interpreter.get("rules") if isinstance(interpreter.get("rules"), dict) else {},
        )

        timeframes = analysis.get("timeframes") or rules.get("timeframes") or interpreter.get("timeframes") or ("D1", "H4", "H1", "M15")
        notes: list[str] = []
        for key in ("description", "summary", "notes"):
            value = raw.get(key)
            if isinstance(value, str) and value.strip():
                notes.append(value.strip())
            elif isinstance(value, list):
                notes.extend(str(item).strip() for item in value if str(item).strip())

        summary = interpreter.get("summary") if isinstance(interpreter.get("summary"), str) else None
        if summary and summary.strip():
            notes.append(summary.strip())

        bias = analysis.get("bias") or rules.get("bias") or "neutral"
        if isinstance(interpreter.get("official_outputs"), list) and interpreter["official_outputs"]:
            bias = str(bias).lower()

        return AnalysisStrategyProfile(
            name=str(interpreter.get("title") or definition.name),
            timeframes=tuple(str(item).upper().strip() for item in timeframes if str(item).strip()),
            minimum_candles=int(analysis.get("minimum_candles", rules.get("minimum_candles", 500))),
            lookback_bars=int(analysis.get("lookback_bars", rules.get("lookback_bars", 120))),
            zone_width_ratio=float(analysis.get("zone_width_ratio", rules.get("zone_width_ratio", 0.35))),
            prefer_recent=bool(analysis.get("prefer_recent", rules.get("prefer_recent", True))),
            bias=str(bias).lower(),
            notes=tuple(notes),
        )

    @staticmethod
    def _merge_mapping(primary: dict[str, Any], secondary: dict[str, Any]) -> dict[str, Any]:
        merged = dict(secondary)
        merged.update(primary)
        return merged
