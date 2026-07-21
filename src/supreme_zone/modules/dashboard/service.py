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
                "frames": [self._frame(frame) for frame in analysis_status.last_report.frame_analyses] if analysis_status.last_report else [],
            },
            "search": {
                "total_scanned": search_engine.state.total_scanned if search_engine else 0,
                "total_hits": search_engine.state.total_hits if search_engine else 0,
                "last_error": search_engine.state.last_error if search_engine else None,
                "hits": [self._hit(hit) for hit in search_engine.hits] if search_engine else [],
            },
            "monitoring": {
                "running": monitoring_engine.state.running if monitoring_engine else False,
                "cycles": monitoring_engine.state.cycles if monitoring_engine else 0,
                "invalidations": monitoring_engine.state.invalidations if monitoring_engine else 0,
                "reanalyses": monitoring_engine.state.reanalyses if monitoring_engine else 0,
                "watchlist": [self._watch(item) for item in monitoring_engine.watchlist] if monitoring_engine else [],
            },
            "execution": {
                "results": len(execution_engine.results) if execution_engine else 0,
                "last_result": self._execution(execution_engine.results[-1]) if execution_engine and execution_engine.results else None,
            },
            "reports": {
                "artifacts": len(report_engine.artifacts) if report_engine else 0,
                "files": [str(path) for path in report_engine.artifacts] if report_engine else [],
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
        payload = json.dumps(snapshot, ensure_ascii=False)
        return f"""<!doctype html>
<html lang=\"ar\" dir=\"rtl\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>{title}</title>
  <style>
    :root {{ color-scheme: dark; }}
    * {{ box-sizing: border-box; }}
    body {{ margin:0; font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background:#020617; color:#e2e8f0; }}
    header {{ position:sticky; top:0; backdrop-filter: blur(12px); background:rgba(2,6,23,.92); border-bottom:1px solid #1e293b; padding:16px 20px; z-index:10; }}
    h1 {{ margin:0 0 8px 0; font-size:24px; }}
    .meta {{ display:flex; gap:12px; flex-wrap:wrap; color:#94a3b8; font-size:14px; }}
    .toolbar {{ display:flex; gap:12px; flex-wrap:wrap; margin-top:14px; }}
    input, button, select {{ background:#0f172a; color:#e2e8f0; border:1px solid #334155; border-radius:12px; padding:10px 12px; }}
    button {{ cursor:pointer; }}
    main {{ padding:20px; max-width:1600px; margin:0 auto; }}
    .grid {{ display:grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap:16px; }}
    .card {{ background: linear-gradient(180deg, #111827, #0f172a); border:1px solid #1f2937; border-radius:20px; padding:16px; box-shadow: 0 10px 24px rgba(0,0,0,.25); }}
    .card h2 {{ margin:0 0 10px 0; font-size:18px; }}
    .stats {{ display:grid; grid-template-columns: repeat(auto-fit,minmax(120px,1fr)); gap:10px; }}
    .stat {{ padding:12px; border:1px solid #334155; border-radius:14px; background:#0b1220; }}
    .stat .label {{ color:#94a3b8; font-size:12px; }}
    .stat .value {{ font-size:20px; font-weight:700; margin-top:4px; }}
    .tabs {{ display:flex; gap:8px; flex-wrap:wrap; margin:16px 0; }}
    .tab {{ padding:10px 14px; border-radius:999px; border:1px solid #334155; background:#0f172a; }}
    .tab.active {{ background:#2563eb; border-color:#2563eb; }}
    .panel {{ display:none; }}
    .panel.active {{ display:block; }}
    pre {{ white-space:pre-wrap; word-break:break-word; margin:0; font-size:13px; line-height:1.55; }}
    .list {{ display:grid; gap:10px; }}
    .item {{ border:1px solid #334155; border-radius:14px; padding:12px; background:#0b1220; }}
    .pill {{ display:inline-block; padding:4px 10px; border-radius:999px; border:1px solid #334155; color:#cbd5e1; margin-inline-end:6px; font-size:12px; }}
  </style>
</head>
<body>
  <header>
    <h1>{title}</h1>
    <div class=\"meta\">
      <span id=\"generatedAt\"></span>
      <span id=\"strategyName\"></span>
      <span id=\"activeSymbol\"></span>
    </div>
    <div class=\"toolbar\">
      <input id=\"searchInput\" placeholder=\"Search zones, symbols, frames...\" />
      <select id=\"sectionSelect\">
        <option value=\"overview\">Overview</option>
        <option value=\"analysis\">Analysis</option>
        <option value=\"search\">Search</option>
        <option value=\"monitoring\">Monitoring</option>
        <option value=\"execution\">Execution</option>
        <option value=\"reports\">Reports</option>
        <option value=\"backtest\">Backtest</option>
      </select>
      <button id=\"refreshBtn\">Refresh</button>
      <button id=\"copyBtn\">Copy JSON</button>
    </div>
  </header>
  <main>
    <section class=\"card\" id=\"overview\"></section>
    <div class=\"tabs\" id=\"tabs\"></div>
    <section id=\"analysisPanel\" class=\"panel card\"></section>
    <section id=\"searchPanel\" class=\"panel card\"></section>
    <section id=\"monitoringPanel\" class=\"panel card\"></section>
    <section id=\"executionPanel\" class=\"panel card\"></section>
    <section id=\"reportsPanel\" class=\"panel card\"></section>
    <section id=\"backtestPanel\" class=\"panel card\"></section>
  </main>
  <script id=\"dashboard-data\" type=\"application/json\">{payload}</script>
  <script>
    const DATA = JSON.parse(document.getElementById('dashboard-data').textContent);
    const panels = ['overview','analysis','search','monitoring','execution','reports','backtest'];
    const tabs = document.getElementById('tabs');
    const searchInput = document.getElementById('searchInput');
    const sectionSelect = document.getElementById('sectionSelect');

    function zone(z) {{
      if (!z) return '<span class="pill">None</span>';
      return `<span class="pill">${{z.side}}</span><span class="pill">${{z.timeframe}}</span><span class="pill">${{Number(z.score).toFixed(2)}}</span><div>${{z.lower}} → ${{z.upper}}</div>`;
    }}

    function renderOverview() {{
      const a = DATA.analysis || {{}};
      const m = DATA.monitoring || {{}};
      const s = DATA.search || {{}};
      const e = DATA.execution || {{}};
      const r = DATA.reports || {{}};
      const b = DATA.backtest || {{}};
      document.getElementById('overview').innerHTML = `
        <h2>Overview</h2>
        <div class="stats">
          <div class="stat"><div class="label">Frames</div><div class="value">${{a.frame_count ?? 0}}</div></div>
          <div class="stat"><div class="label">Search Hits</div><div class="value">${{s.total_hits ?? 0}}</div></div>
          <div class="stat"><div class="label">Monitoring Cycles</div><div class="value">${{m.cycles ?? 0}}</div></div>
          <div class="stat"><div class="label">Execution Results</div><div class="value">${{e.results ?? 0}}</div></div>
          <div class="stat"><div class="label">Reports</div><div class="value">${{r.artifacts ?? 0}}</div></div>
          <div class="stat"><div class="label">Backtest Runs</div><div class="value">${{b.runs ?? 0}}</div></div>
        </div>`;
    }}

    function renderAnalysis(filter = '') {{
      const a = DATA.analysis || {{}};
      const frames = (a.frames || []).filter(frame => JSON.stringify(frame).toLowerCase().includes(filter));
      document.getElementById('analysisPanel').innerHTML = `
        <h2>Analysis</h2>
        <div class="item"><strong>BUY</strong><div>${{zone(a.buy_zone)}}</div></div>
        <div class="item"><strong>SELL</strong><div>${{zone(a.sell_zone)}}</div></div>
        <div class="list">${{frames.map(frame => `<div class="item"><strong>${{frame.timeframe}}</strong><pre>${{JSON.stringify(frame, null, 2)}}</pre></div>`).join('')}}</div>`;
    }}

    function renderSearch(filter = '') {{
      const hits = (DATA.search?.hits || []).filter(hit => JSON.stringify(hit).toLowerCase().includes(filter));
      document.getElementById('searchPanel').innerHTML = `
        <h2>Search</h2>
        <div class="list">${{hits.map(hit => `<div class="item"><strong>${{hit.symbol}}</strong><pre>${{JSON.stringify(hit, null, 2)}}</pre></div>`).join('') || '<div class="item">No hits</div>'}}</div>`;
    }}

    function renderMonitoring(filter = '') {{
      const watch = (DATA.monitoring?.watchlist || []).filter(item => JSON.stringify(item).toLowerCase().includes(filter));
      document.getElementById('monitoringPanel').innerHTML = `
        <h2>Monitoring</h2>
        <div class="list">${{watch.map(item => `<div class="item"><strong>${{item.symbol}}</strong><pre>${{JSON.stringify(item, null, 2)}}</pre></div>`).join('') || '<div class="item">No watchlist items</div>'}}</div>`;
    }}

    function renderExecution(filter = '') {{
      const result = DATA.execution?.last_result;
      document.getElementById('executionPanel').innerHTML = `
        <h2>Execution</h2>
        <div class="item"><pre>${{result ? JSON.stringify(result, null, 2) : 'No execution results'}}</pre></div>`;
    }}

    function renderReports(filter = '') {{
      const files = (DATA.reports?.files || []).filter(item => item.toLowerCase().includes(filter));
      document.getElementById('reportsPanel').innerHTML = `
        <h2>Reports</h2>
        <div class="list">${{files.map(file => `<div class="item">${{file}}</div>`).join('') || '<div class="item">No reports</div>'}}</div>`;
    }}

    function renderBacktest(filter = '') {{
      const b = DATA.backtest || {{}};
      document.getElementById('backtestPanel').innerHTML = `
        <h2>Backtest</h2>
        <div class="stats">
          <div class="stat"><div class="label">Runs</div><div class="value">${{b.runs ?? 0}}</div></div>
          <div class="stat"><div class="label">Last Error</div><div class="value">${{b.last_error ? '1' : '0'}}</div></div>
        </div>`;
    }}

    function setActive(section) {{
      panels.forEach(p => document.getElementById(p === 'overview' ? 'overview' : p + 'Panel').classList.remove('active'));
      const panelId = section === 'overview' ? 'overview' : section + 'Panel';
      document.getElementById(panelId).classList.add('active');
      [...tabs.children].forEach(btn => btn.classList.toggle('active', btn.dataset.section === section));
      sectionSelect.value = section;
    }}

    function renderTabs() {{
      const names = ['overview','analysis','search','monitoring','execution','reports','backtest'];
      tabs.innerHTML = names.map(name => `<button class="tab" data-section="${{name}}">${{name.toUpperCase()}}</button>`).join('');
      tabs.querySelectorAll('button').forEach(btn => btn.addEventListener('click', () => setActive(btn.dataset.section)));
    }}

    function applyFilter() {{
      const filter = searchInput.value.trim().toLowerCase();
      renderAnalysis(filter);
      renderSearch(filter);
      renderMonitoring(filter);
      renderExecution(filter);
      renderReports(filter);
      renderBacktest(filter);
    }}

    document.getElementById('generatedAt').textContent = `Generated: ${{DATA.generated_at || ''}}`;
    document.getElementById('strategyName').textContent = `Strategy: ${{DATA.analysis?.strategy_name || 'N/A'}}`;
    document.getElementById('activeSymbol').textContent = `Symbol: ${{DATA.analysis?.symbol || 'N/A'}}`;
    document.getElementById('refreshBtn').addEventListener('click', () => location.reload());
    document.getElementById('copyBtn').addEventListener('click', async () => {{ await navigator.clipboard.writeText(JSON.stringify(DATA, null, 2)); }});
    searchInput.addEventListener('input', applyFilter);
    sectionSelect.addEventListener('change', e => setActive(e.target.value));

    renderTabs();
    renderOverview();
    applyFilter();
    setActive('overview');
  </script>
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

    def _frame(self, frame) -> dict[str, Any]:
        return {
            "symbol": frame.symbol,
            "timeframe": frame.timeframe,
            "trend": frame.trend,
            "volatility": frame.volatility,
            "buy_candidate": self._zone(frame.buy_candidate),
            "sell_candidate": self._zone(frame.sell_candidate),
            "notes": frame.notes,
        }

    def _hit(self, hit) -> dict[str, Any]:
        return {
            "symbol": hit.symbol,
            "candidate": self._zone(hit.candidate),
            "validation": {
                "status": hit.validation.status.value if hit.validation else None,
                "is_valid": hit.validation.is_valid if hit.validation else None,
                "consumed": hit.validation.consumed if hit.validation else None,
            } if hit.validation else None,
        }

    def _watch(self, item) -> dict[str, Any]:
        return {
            "symbol": item.symbol,
            "candidate": self._zone(item.candidate),
            "validation": item.validation.status.value if item.validation else None,
            "entry": item.entry.status.value if item.entry else None,
        }

    def _execution(self, result) -> dict[str, Any]:
        if result is None:
            return {}
        return {
            "status": result.status.value,
            "error": result.error,
            "request": {
                "symbol": result.request.symbol,
                "side": result.request.side.value,
                "volume": result.request.volume,
                "stop_loss": result.request.stop_loss,
                "take_profit": result.request.take_profit,
            },
        }

    @property
    def artifacts(self) -> tuple[Path, ...]:
        return tuple(self._artifacts)
