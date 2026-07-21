from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from ..analysis_engine.models import AnalysisReport
from ..entry_engine.models import EntrySignal
from ..execution_engine.models import TradeResult
from ..validation_engine.models import ZoneValidationResult
from .models import ReportArtifact, ReportBundle


@dataclass(slots=True)
class ReportEngine:
    output_dir: Path
    _artifacts: list[ReportArtifact] = field(default_factory=list, init=False)

    def generate(self, bundle: ReportBundle) -> ReportArtifact:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        stamp = bundle.created_at.strftime("%Y%m%d_%H%M%S")
        base_name = f"{bundle.symbol.upper()}_{stamp}"
        json_path = self.output_dir / f"{base_name}.json"
        markdown_path = self.output_dir / f"{base_name}.md"
        summary_path = self.output_dir / f"{base_name}_summary.txt"

        payload = self._serialize(bundle)
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        markdown_path.write_text(self._render_markdown(payload), encoding="utf-8")
        summary_path.write_text(self._render_summary(payload), encoding="utf-8")

        artifact = ReportArtifact(json_path=json_path, markdown_path=markdown_path, summary_path=summary_path)
        self._artifacts.append(artifact)
        return artifact

    def _serialize(self, bundle: ReportBundle) -> dict[str, Any]:
        return {
            "symbol": bundle.symbol,
            "created_at": bundle.created_at.isoformat(),
            "analysis": self._serialize_analysis(bundle.analysis),
            "validation": {key: self._serialize_validation(value) for key, value in bundle.validation.items()},
            "entry": self._serialize_entry(bundle.entry) if bundle.entry is not None else None,
            "execution": self._serialize_execution(bundle.execution) if bundle.execution is not None else None,
            "backtest": bundle.backtest,
        }

    def _serialize_analysis(self, analysis: AnalysisReport) -> dict[str, Any]:
        return {
            "symbol": analysis.symbol,
            "strategy_name": analysis.strategy_name,
            "buy_zone": self._serialize_zone(analysis.buy_zone),
            "sell_zone": self._serialize_zone(analysis.sell_zone),
            "metadata": analysis.metadata,
            "frames": [
                {
                    "symbol": frame.symbol,
                    "timeframe": frame.timeframe,
                    "trend": frame.trend,
                    "volatility": frame.volatility,
                    "buy_candidate": self._serialize_zone(frame.buy_candidate),
                    "sell_candidate": self._serialize_zone(frame.sell_candidate),
                    "notes": frame.notes,
                }
                for frame in analysis.frame_analyses
            ],
        }

    def _serialize_zone(self, zone) -> dict[str, Any] | None:
        if zone is None:
            return None
        return {
            "side": zone.side.value,
            "timeframe": zone.timeframe,
            "symbol": zone.symbol,
            "lower": zone.lower,
            "upper": zone.upper,
            "score": zone.score,
            "source": zone.source,
            "evidence": zone.evidence,
        }

    def _serialize_validation(self, validation: ZoneValidationResult) -> dict[str, Any]:
        return {
            "status": validation.status.value,
            "is_valid": validation.is_valid,
            "touched": validation.touched,
            "consumed": validation.consumed,
            "invalid_reason": validation.invalid_reason,
            "evidence": validation.evidence,
            "metadata": validation.metadata,
        }

    def _serialize_entry(self, entry: EntrySignal) -> dict[str, Any]:
        return {
            "status": entry.status.value,
            "side": entry.side.value,
            "entry_price": entry.entry_price,
            "stop_loss": entry.stop_loss,
            "take_profit": entry.take_profit,
            "candidate": self._serialize_zone(entry.candidate),
            "evidence": entry.evidence,
            "metadata": entry.metadata,
        }

    def _serialize_execution(self, execution: TradeResult) -> dict[str, Any]:
        return {
            "status": execution.status.value,
            "error": execution.error,
            "broker_response": execution.broker_response,
            "request": {
                "symbol": execution.request.symbol,
                "side": execution.request.side.value,
                "volume": execution.request.volume,
                "stop_loss": execution.request.stop_loss,
                "take_profit": execution.request.take_profit,
                "comment": execution.request.comment,
                "magic": execution.request.magic,
            },
        }

    def _render_markdown(self, payload: dict[str, Any]) -> str:
        lines = [
            f"# Analysis Report: {payload['symbol']}",
            f"- Created at: {payload['created_at']}",
            f"- Strategy: {payload['analysis']['strategy_name']}",
            "",
            "## BUY ZONE",
            self._zone_markdown(payload["analysis"]["buy_zone"]),
            "",
            "## SELL ZONE",
            self._zone_markdown(payload["analysis"]["sell_zone"]),
            "",
            "## Frames",
        ]
        for frame in payload["analysis"]["frames"]:
            lines.extend([
                f"### {frame['timeframe']}",
                f"- Trend: {frame['trend']}",
                f"- Volatility: {frame['volatility']}",
                f"- BUY Candidate: {frame['buy_candidate']['lower'] if frame['buy_candidate'] else 'N/A'}",
                f"- SELL Candidate: {frame['sell_candidate']['upper'] if frame['sell_candidate'] else 'N/A'}",
                "",
            ])
        return "\n".join(lines)

    def _zone_markdown(self, zone: dict[str, Any] | None) -> str:
        if zone is None:
            return "- None"
        return f"- {zone['side']} {zone['timeframe']} {zone['lower']:.6f} → {zone['upper']:.6f} | score={zone['score']}"

    def _render_summary(self, payload: dict[str, Any]) -> str:
        return (
            f"symbol={payload['symbol']}\n"
            f"strategy={payload['analysis']['strategy_name']}\n"
            f"buy={payload['analysis']['buy_zone']}\n"
            f"sell={payload['analysis']['sell_zone']}\n"
        )

    @property
    def artifacts(self) -> tuple[ReportArtifact, ...]:
        return tuple(self._artifacts)
