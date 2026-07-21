from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Any

from ..analysis_engine.models import AnalysisReport, ZoneCandidate, ZoneSide
from ..data_engine.market import MarketBar
from .models import ValidationStatus, ZoneValidationResult


@dataclass(slots=True)
class ValidationEngine:
    tolerance_ratio: float = 0.2
    _last_results: dict[str, ZoneValidationResult] = field(default_factory=dict)

    def validate_candidate(self, candidate: ZoneCandidate, bars: Iterable[MarketBar], audit: Any | None = None) -> ZoneValidationResult:
        bar_list = tuple(bars)
        if not bar_list:
            result = ZoneValidationResult(candidate, ValidationStatus.INVALID, False, False, False, "no-bars", (), {})
            self._last_results[self._key(candidate)] = result
            return result

        latest = bar_list[-1]
        touched = self._touched(candidate, latest)
        consumed = self._consumed(candidate, latest)
        governance_passed = bool(audit.get("passed", False)) if isinstance(audit, dict) else True
        governance_score = int(audit.get("score", 0)) if isinstance(audit, dict) else None
        valid = governance_passed and not consumed and candidate.lower < candidate.upper and candidate.score > 0

        if not valid:
            status = ValidationStatus.INVALID
            reason = "invalid-zone" if not governance_passed else ("consumed" if consumed else "invalid-zone")
        elif consumed:
            status = ValidationStatus.CONSUMED
            reason = "consumed"
        elif touched:
            status = ValidationStatus.MITIGATED
            reason = "touched"
        else:
            status = ValidationStatus.FRESH
            reason = None

        evidence = [
            f"latest_close={latest.close}",
            f"zone={candidate.lower:.6f}:{candidate.upper:.6f}",
            f"status={status.value}",
        ]
        if governance_score is not None:
            evidence.append(f"governance_score={governance_score}")
        if isinstance(audit, dict):
            evidence.append(f"governance_passed={audit.get('passed')}")

        result = ZoneValidationResult(
            candidate=candidate,
            status=status,
            is_valid=valid,
            touched=touched,
            consumed=consumed,
            invalid_reason=reason,
            evidence=tuple(evidence),
            metadata={"last_time": latest.time.isoformat(), "governance": audit or {}},
        )
        self._last_results[self._key(candidate)] = result
        return result

    def validate_report(self, report: AnalysisReport, bars_by_timeframe: dict[str, Iterable[MarketBar]]) -> tuple[ZoneValidationResult, ZoneValidationResult]:
        governance = report.metadata.get("governance", {}) if isinstance(report.metadata, dict) else {}
        buy_audit = governance.get(report.buy_zone.timeframe, {}).get("buy") if report.buy_zone else None
        sell_audit = governance.get(report.sell_zone.timeframe, {}).get("sell") if report.sell_zone else None
        buy_result = self.validate_candidate(report.buy_zone, bars_by_timeframe.get(report.buy_zone.timeframe, ()), audit=buy_audit) if report.buy_zone else None
        sell_result = self.validate_candidate(report.sell_zone, bars_by_timeframe.get(report.sell_zone.timeframe, ()), audit=sell_audit) if report.sell_zone else None
        return buy_result, sell_result

    def validate_active_zones(self, report: AnalysisReport, bars_by_timeframe: dict[str, Iterable[MarketBar]]) -> dict[str, ZoneValidationResult]:
        results: dict[str, ZoneValidationResult] = {}
        governance = report.metadata.get("governance", {}) if isinstance(report.metadata, dict) else {}
        if report.buy_zone is not None:
            buy_audit = governance.get(report.buy_zone.timeframe, {}).get("buy")
            results["buy"] = self.validate_candidate(report.buy_zone, bars_by_timeframe.get(report.buy_zone.timeframe, ()), audit=buy_audit)
        if report.sell_zone is not None:
            sell_audit = governance.get(report.sell_zone.timeframe, {}).get("sell")
            results["sell"] = self.validate_candidate(report.sell_zone, bars_by_timeframe.get(report.sell_zone.timeframe, ()), audit=sell_audit)
        return results

    def last_result(self, candidate: ZoneCandidate) -> ZoneValidationResult | None:
        return self._last_results.get(self._key(candidate))

    def _key(self, candidate: ZoneCandidate) -> str:
        return f"{candidate.symbol}:{candidate.timeframe}:{candidate.side.value}:{candidate.lower:.8f}:{candidate.upper:.8f}"

    def _touched(self, candidate: ZoneCandidate, bar: MarketBar) -> bool:
        return bar.low <= candidate.upper and bar.high >= candidate.lower

    def _consumed(self, candidate: ZoneCandidate, bar: MarketBar) -> bool:
        span = max(candidate.width, 1e-9)
        threshold = span * (1.0 + self.tolerance_ratio)
        if candidate.side is ZoneSide.BUY:
            return bar.close < candidate.lower - threshold
        return bar.close > candidate.upper + threshold
