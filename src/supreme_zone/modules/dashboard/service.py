from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..analysis_engine.service import AnalysisEngine
from ..backtest_engine.service import BacktestEngine
from ..execution_engine.service import ExecutionEngine
from ..monitoring_engine.service import MonitoringEngine
from ..report_engine.service import ReportEngine
from ..search_engine.service import SearchEngine


@dataclass(slots=True)
class DashboardService:
    output_dir: Path
    _artifacts: list[Path] = field(default_factory=list, init=False)

    def snapshot(
        self,
        analysis_engine: AnalysisEngine,
        search_engine: SearchEngine | None = None,
        monitoring_engine: MonitoringEngine | None = None,
        execution_engine: ExecutionEngine | None = None,
        report_engine: ReportEngine | None = None,
        backtest_engine: BacktestEngine | None = None,
    ) -> dict[str, Any]:
        analysis_status = analysis_engine.status
        snapshot = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "analysis": {
                "strategy_name": analysis_status.strategy_name,
                "symbol": analysis_status.analyzed_symbol,
                "timeframes": analysis_status.analyzed_timeframes,
                "frame_count": analysis_status.frame_count,
                "buy_zone": self._zone(analysis_status.last_report.buy_zone) if analysis_status.last_report else None,
                "sell_zone": self._zone(analysis_status.last_report.sell_zone) if analysis_status.last_report else None,
            },
            "search": {
                "total_scanned": search_engine.state.total_scanned if search_engine else 0,
                "total_hits": search_engine.state.total_hits if search_engine else 0,
                "last_error": search_engine.state.last_error if search_engine else None,
            },
            "monitoring": {
                "running": monitoring_engine.state.running if monitoring_engine else False,
                "cycles": monitoring_engine.state.cycles if monitoring_engine else 0,
                "invalidations": monitoring_engine.state.invalidations if monitoring_engine else 0,
                "reanalyses": monitoring_engine.state.reanalyses if monitoring_engine else 0,
            },
            "execution": {
                "results": len(execution_engine.results) if execution_engine else 0,
            },
            "reports": {
                "artifacts": len(report_engine.artifacts) if report_engine else 0,
            },
            "backtest": {
                "runs": backtest_engine.state.runs if backtest_engine else 0,
                "last_error": backtest_engine.state.last_error if backtest_engine else None,
            },
        }
        return snapshot

    def render(self, snapshot: dict[str, Any], title: str = "Supreme Zone Platform Dashboard") -> Path:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        html_path = self.output_dir / "dashboard.html"
        html_path.write_text(self._render_html(snapshot, title), encoding="utf-8")
        self._artifacts.append(html_path)
        return html_path

    def export_json(self, snapshot: dict[str, Any]) -> Path:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        json_path = self.output_dir / "dashboard.json"
        json_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
        self._artifacts.append(json_path)
        return json_path

    def _render_html(self, snapshot: dict[str, Any], title: str) -> str:
        analysis = snapshot["analysis"]
        return f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>{title}</title>
  <style>
    body {{ font-family: Arial, sans-serif; background:#0f172a; color:#e2e8f0; margin:0; padding:24px; }}
    .grid {{ display:grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap:16px; }}
    .card {{ background:#111827; border:1px solid #334155; border-radius:16px; padding:16px; }}
    h1, h2, h3 {{ margin-top:0; }}
    pre {{ white-space: pre-wrap; word-break: break-word; }}
  </style>
</head>
<body>
  <h1>{title}</h1>
  <div class=\"grid\">
    <div class=\"card\"><h3>Analysis</h3><pre>{json.dumps(analysis, ensure_ascii=False, indent=2)}</pre></div>
    <div class=\"card\"><h3>Search</h3><pre>{json.dumps(snapshot['search'], ensure_ascii=False, indent=2)}</pre></div>
    <div class=\"card\"><h3>Monitoring</h3><pre>{json.dumps(snapshot['monitoring'], ensure_ascii=False, indent=2)}</pre></div>
    <div class=\"card\"><h3>Execution</h3><pre>{json.dumps(snapshot['execution'], ensure_ascii=False, indent=2)}</pre></div>
    <div class=\"card\"><h3>Reports</h3><pre>{json.dumps(snapshot['reports'], ensure_ascii=False, indent=2)}</pre></div>
    <div class=\"card\"><h3>Backtest</h3><pre>{json.dumps(snapshot['backtest'], ensure_ascii=False, indent=2)}</pre></div>
  </div>
</body>
</html>"""

    def _zone(self, zone) -> dict[str, Any] | None:
        if zone is None:
            return None
        return {
            "side": zone.side.value,
            "timeframe": zone.timeframe,
            "lower": zone.lower,
            "upper": zone.upper,
            "score": zone.score,
        }

    @property
    def artifacts(self) -> tuple[Path, ...]:
        return tuple(self._artifacts)
