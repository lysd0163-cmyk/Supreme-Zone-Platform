from __future__ import annotations

import json
from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse

from .core.bootstrap import bootstrap
from .core.platform import SupremeZonePlatform


@asynccontextmanager
async def lifespan(app: FastAPI):
    bootstrap_result = bootstrap()
    app.state.bootstrap_result = bootstrap_result
    app.state.platform = bootstrap_result.platform
    app.state.runtime = {
        "strategy_path": None,
        "symbols": tuple(),
        "timeframes": tuple(),
        "bars": None,
        "data_source": getattr(bootstrap_result.platform.data_engine, "data_source", "mt5"),
    }
    yield


app = FastAPI(
    title="Supreme Zone Platform",
    version="0.1.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_platform() -> SupremeZonePlatform:
    platform = getattr(app.state, "platform", None)
    if not isinstance(platform, SupremeZonePlatform):
        raise HTTPException(status_code=503, detail="Platform is not ready")
    return platform


def _safe_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_safe_json(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _bootstrap_payload() -> dict[str, Any]:
    bootstrap_result = getattr(app.state, "bootstrap_result", None)
    if bootstrap_result is None:
        return {}
    return {
        "ready": bool(getattr(bootstrap_result, "ready", False)),
        "app_name": getattr(bootstrap_result, "app_name", "Supreme Zone Platform"),
        "config_path": str(getattr(bootstrap_result, "config_path", "config/default.yaml")),
        "storage_root": str(getattr(bootstrap_result, "storage_root", "storage")),
        "services_registered": list(getattr(bootstrap_result, "services_registered", ())),
    }


def _strategy_payload(strategy) -> dict[str, Any]:
    if strategy is None:
        return {}
    return {
        "name": strategy.name,
        "version": strategy.version,
        "source_path": str(strategy.source_path),
        "active": bool(strategy.active),
        "raw": _safe_json(strategy.raw),
    }


def _strategies_payload() -> dict[str, Any]:
    platform = _get_platform()
    manager = platform.analysis_engine.strategy_manager
    active = manager.get_active_strategy()
    strategies = sorted(manager.list_strategies(), key=lambda item: (item.name.lower(), item.version))
    history = manager.strategy_history()
    history_payload: dict[str, list[dict[str, Any]]] = {}
    if isinstance(history, dict):
        for name, versions in history.items():
            history_payload[name] = [_strategy_payload(version) for version in versions]
    else:
        history_payload = {active.name: [_strategy_payload(item) for item in history]} if active is not None else {}
    return {
        "active": _strategy_payload(active) if active is not None else None,
        "strategies": [_strategy_payload(strategy) for strategy in strategies],
        "history": history_payload,
    }


def _data_config_payload() -> dict[str, Any]:
    platform = _get_platform()
    engine = platform.data_engine
    settings = engine.settings
    runtime = getattr(app.state, "runtime", {})
    return {
        "source": engine.data_source,
        "symbols": list(engine.symbol_manager.symbols or settings.symbols),
        "timeframes": list(engine.timeframe_manager.supported or settings.timeframes),
        "bars": runtime.get("bars") or settings.market.history_window_candles,
        "api_key_present": bool(engine.twelve_data_api_key),
        "base_url": engine.twelve_data_base_url,
        "mt5_enabled": settings.mt5.enabled,
        "mt5_accounts": [
            {
                "label": account.label,
                "server": account.server,
                "login": account.login,
                "complete": account.is_complete,
            }
            for account in settings.mt5.accounts
        ],
    }


def _history_payload(limit: int = 20) -> dict[str, Any]:
    platform = _get_platform()
    db = platform.data_engine.database
    return {
        "sync_runs": db.recent_sync_runs(limit=limit),
        "charts": db.recent_charts(limit=limit),
        "errors": db.recent_errors(limit=limit),
        "summary": db.summary(),
    }


def _apply_runtime_market_config(symbols: tuple[str, ...], timeframes: tuple[str, ...], bars: int | None) -> None:
    platform = _get_platform()
    engine = platform.data_engine
    settings = engine.settings
    minimum = max(settings.market.minimum_candles, bars or settings.market.minimum_candles)
    history = max(settings.market.history_window_candles, bars or settings.market.history_window_candles)
    updated_settings = replace(
        settings,
        market=replace(
            settings.market,
            symbols=symbols,
            timeframes=timeframes,
            minimum_candles=minimum,
            history_window_candles=history,
        ),
    )
    engine.settings = updated_settings
    platform.analysis_engine.settings = updated_settings
    engine.symbol_manager.load(symbols)
    engine.timeframe_manager.load(timeframes)
    app.state.runtime["symbols"] = symbols
    app.state.runtime["timeframes"] = timeframes
    app.state.runtime["bars"] = bars


def _render_dashboard_html(snapshot: dict[str, Any], strategies: dict[str, Any], data_config: dict[str, Any], history: dict[str, Any]) -> str:
    payload = json.dumps(
        _safe_json(
            {
                "snapshot": snapshot,
                "strategies": strategies,
                "data_config": data_config,
                "history": history,
                "boot": _bootstrap_payload(),
            }
        ),
        ensure_ascii=False,
        default=str,
    )
    active_strategy = strategies.get("active") or {}
    selected_symbols = ", ".join(data_config.get("symbols", []))
    selected_timeframes = ", ".join(data_config.get("timeframes", []))
    source = data_config.get("source", "mt5")
    return f"""<!doctype html>
<html lang="ar" dir="rtl">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Supreme Zone Platform Dashboard</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f8fafc;
      --surface: #ffffff;
      --surface-2: #f1f5f9;
      --border: #dbe4f0;
      --text: #0f172a;
      --muted: #64748b;
      --primary: #2563eb;
      --primary-weak: #dbeafe;
      --success: #16a34a;
      --warning: #f59e0b;
      --danger: #ef4444;
      --shadow: 0 16px 40px rgba(15,23,42,.08);
      --radius: 22px;
    }}
    * {{ box-sizing: border-box; }}
    html, body {{ margin:0; padding:0; background:var(--bg); color:var(--text); font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    body {{ min-height:100vh; }}
    a {{ color: inherit; }}
    .shell {{ max-width: 1600px; margin: 0 auto; padding: 18px; }}
    .hero {{ background: linear-gradient(180deg, #ffffff, #f8fbff); border:1px solid var(--border); border-radius: 28px; box-shadow: var(--shadow); padding: 22px; }}
    .hero-top {{ display:flex; justify-content:space-between; gap:16px; flex-wrap:wrap; align-items:flex-start; }}
    .title {{ font-size: clamp(28px, 4vw, 44px); line-height:1.05; margin:0; }}
    .subtitle {{ color:var(--muted); margin-top:8px; font-size:14px; }}
    .status-row {{ display:flex; gap:10px; flex-wrap:wrap; margin-top:16px; }}
    .chip {{ display:inline-flex; align-items:center; gap:8px; padding:10px 14px; border-radius:999px; border:1px solid var(--border); background:var(--surface); font-size:13px; }}
    .chip strong {{ font-size:14px; }}
    .toolbar {{ display:flex; gap:10px; flex-wrap:wrap; margin-top:18px; }}
    .btn {{ border:1px solid var(--border); background:var(--surface); color:var(--text); border-radius: 16px; padding: 12px 16px; font-weight:600; cursor:pointer; box-shadow: 0 4px 12px rgba(15,23,42,.04); }}
    .btn.primary {{ background: var(--primary); color: white; border-color: var(--primary); }}
    .btn.ghost {{ background: var(--surface-2); }}
    .controls {{ display:grid; gap:14px; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); margin-top:18px; }}
    .card {{ background: var(--surface); border:1px solid var(--border); border-radius: var(--radius); box-shadow: var(--shadow); padding: 18px; }}
    .card h2 {{ margin:0 0 12px 0; font-size:20px; }}
    .grid {{ display:grid; gap:14px; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); }}
    .stat {{ background: #f8fbff; border:1px solid var(--border); border-radius:18px; padding: 16px; }}
    .stat .label {{ color: var(--muted); font-size:12px; margin-bottom:8px; }}
    .stat .value {{ font-size: 26px; font-weight: 800; }}
    .section-tabs {{ display:flex; gap:10px; flex-wrap:wrap; margin:18px 0; }}
    .tab {{ padding:10px 14px; border:1px solid var(--border); background:var(--surface); border-radius:999px; cursor:pointer; font-weight:700; }}
    .tab.active {{ background: var(--primary); color:white; border-color: var(--primary); }}
    .panel {{ display:none; }}
    .panel.active {{ display:block; }}
    .field-grid {{ display:grid; gap:12px; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); }}
    label {{ display:block; font-size:12px; color:var(--muted); margin-bottom:6px; }}
    input, select, textarea {{ width:100%; padding:12px 14px; border:1px solid var(--border); border-radius:14px; background:var(--surface); color:var(--text); }}
    textarea {{ min-height: 90px; resize: vertical; }}
    .list {{ display:grid; gap:12px; }}
    .item {{ border:1px solid var(--border); border-radius:18px; padding:14px; background:#fff; }}
    .item strong {{ display:block; margin-bottom:6px; }}
    .pill {{ display:inline-block; padding:4px 10px; border-radius:999px; background:var(--primary-weak); color:var(--primary); font-size:12px; margin-inline-end:6px; margin-bottom:6px; }}
    .muted {{ color: var(--muted); }}
    .footer {{ color: var(--muted); font-size:12px; margin: 22px 0 12px; text-align:center; }}
    .mini {{ font-size:12px; color:var(--muted); }}
    pre {{ margin:0; white-space:pre-wrap; word-break:break-word; font-size:12px; line-height:1.6; }}
  </style>
</head>
<body>
  <div class="shell">
    <section class="hero">
      <div class="hero-top">
        <div>
          <h1 class="title">Supreme Zone Platform</h1>
          <div class="subtitle">لوحة تحكم بيضاء حديثة لإضافة الاستراتيجية، ضبط مصدر البيانات، تحليل الأزواج، ومراقبة الزونات مباشرة.</div>
          <div class="status-row">
            <span class="chip">الحالة: <strong id="bootReady">جاهز</strong></span>
            <span class="chip">الاستراتيجية: <strong id="activeStrategy">{escape(active_strategy.get('name', 'N/A') or 'N/A')}</strong></span>
            <span class="chip">المصدر: <strong id="activeSource">{escape(str(source))}</strong></span>
            <span class="chip">الأزواج: <strong id="activeSymbols">{escape(selected_symbols or 'N/A')}</strong></span>
            <span class="chip">الفريمات: <strong id="activeTimeframes">{escape(selected_timeframes or 'N/A')}</strong></span>
          </div>
        </div>
        <div>
          <div class="toolbar">
            <button class="btn primary" id="runBtn">بدء التشغيل / Analyze</button>
            <button class="btn" id="syncBtn">جلب البيانات</button>
            <button class="btn" id="startMonBtn">بدء المراقبة</button>
            <button class="btn" id="stopMonBtn">إيقاف المراقبة</button>
            <button class="btn ghost" id="refreshBtn">تحديث</button>
          </div>
        </div>
      </div>
      <div class="grid" style="margin-top:18px;">
        <div class="stat"><div class="label">الأزواج المحللة</div><div class="value" id="statAnalyzed">0</div></div>
        <div class="stat"><div class="label">الصفقات المفتوحة</div><div class="value" id="statOpenPositions">0</div></div>
        <div class="stat"><div class="label">الزونات النشطة</div><div class="value" id="statZones">0</div></div>
        <div class="stat"><div class="label">آخر التحليلات</div><div class="value" id="statReports">0</div></div>
        <div class="stat"><div class="label">سرعة المحرك</div><div class="value" id="statCycles">0</div></div>
        <div class="stat"><div class="label">حالة المراقبة</div><div class="value" id="statMonitoring">0</div></div>
      </div>
    </section>

    <div class="section-tabs">
      <button class="tab active" data-panel="overviewPanel">Overview</button>
      <button class="tab" data-panel="strategyPanel">Strategy Manager</button>
      <button class="tab" data-panel="dataPanel">Data Center</button>
      <button class="tab" data-panel="analysisPanel">Analysis</button>
      <button class="tab" data-panel="reportsPanel">Reports</button>
      <button class="tab" data-panel="monitoringPanel">Monitoring</button>
      <button class="tab" data-panel="historyPanel">History</button>
      <button class="tab" data-panel="settingsPanel">Settings</button>
    </div>

    <section class="panel active" id="overviewPanel">
      <div class="card">
        <h2>Overview</h2>
        <div class="grid" id="overviewGrid"></div>
      </div>
    </section>

    <section class="panel" id="strategyPanel">
      <div class="card">
        <h2>Strategy Manager</h2>
        <form id="strategyForm" class="field-grid">
          <div>
            <label>رفع ملف الاستراتيجية (PDF / JSON / TXT / MD / YAML)</label>
            <input type="file" id="strategyFile" accept=".pdf,.json,.txt,.md,.yaml,.yml" required />
          </div>
          <div>
            <label>بعد الرفع</label>
            <select id="activateStrategy">
              <option value="true">تفعيلها مباشرة</option>
              <option value="false">رفع فقط</option>
            </select>
          </div>
          <div style="grid-column:1/-1; display:flex; gap:10px; flex-wrap:wrap; align-items:center;">
            <button class="btn primary" type="submit">➕ إضافة استراتيجية</button>
            <button class="btn" type="button" id="deactivateStrategyBtn">إيقاف الاستراتيجية النشطة</button>
          </div>
        </form>
        <div class="grid" style="margin-top:18px;">
          <div class="item">
            <strong>الاستراتيجية النشطة</strong>
            <div id="activeStrategyCard"></div>
          </div>
          <div class="item">
            <strong>الإصدارات</strong>
            <div id="strategyHistory" class="list"></div>
          </div>
        </div>
      </div>
    </section>

    <section class="panel" id="dataPanel">
      <div class="card">
        <h2>Data Center</h2>
        <form id="dataForm" class="field-grid">
          <div>
            <label>مصدر البيانات</label>
            <select id="dataSource">
              <option value="twelve_data">Twelve Data</option>
              <option value="mt5">MT5</option>
            </select>
          </div>
          <div>
            <label>عدد الشموع</label>
            <input id="barsInput" type="number" min="50" step="1" value="{int(data_config.get('bars') or 500)}" />
          </div>
          <div>
            <label>الأزواج (مفصولة بفاصلة)</label>
            <input id="symbolsInput" type="text" value="{escape(selected_symbols)}" placeholder="EURUSD,GBPUSD,XAUUSD" />
          </div>
          <div>
            <label>الفريمات (مفصولة بفاصلة)</label>
            <input id="timeframesInput" type="text" value="{escape(selected_timeframes)}" placeholder="D1,H4,H1,M15" />
          </div>
          <div>
            <label>Twelve Data API Key</label>
            <input id="apiKeyInput" type="password" value="{escape('***' if data_config.get('api_key_present') else '')}" placeholder="ضع المفتاح هنا" />
          </div>
          <div>
            <label>Base URL</label>
            <input id="baseUrlInput" type="text" value="{escape(str(data_config.get('base_url') or 'https://api.twelvedata.com/time_series'))}" />
          </div>
          <div style="grid-column:1/-1; display:flex; gap:10px; flex-wrap:wrap; align-items:center;">
            <button class="btn primary" type="submit">حفظ إعدادات البيانات</button>
            <button class="btn" type="button" id="syncNowBtn">مزامنة فورية</button>
          </div>
        </form>
      </div>
    </section>

    <section class="panel" id="analysisPanel">
      <div class="card">
        <h2>Analysis</h2>
        <div class="grid">
          <div class="item"><strong>BUY ZONE</strong><div id="buyZoneBox"></div></div>
          <div class="item"><strong>SELL ZONE</strong><div id="sellZoneBox"></div></div>
        </div>
        <div class="list" style="margin-top:14px;" id="analysisFrames"></div>
      </div>
    </section>

    <section class="panel" id="reportsPanel">
      <div class="card">
        <h2>Reports</h2>
        <div class="grid">
          <div class="item"><strong>آخر التقارير</strong><div id="reportCount"></div></div>
          <div class="item"><strong>الملفات</strong><div id="reportFiles" class="list"></div></div>
        </div>
      </div>
    </section>

    <section class="panel" id="monitoringPanel">
      <div class="card">
        <h2>Monitoring</h2>
        <div class="grid">
          <div class="item"><strong>الحالة</strong><div id="monitorStatus"></div></div>
          <div class="item"><strong>Watchlist</strong><div id="watchlistBox" class="list"></div></div>
        </div>
      </div>
    </section>

    <section class="panel" id="historyPanel">
      <div class="card">
        <h2>History</h2>
        <div class="grid">
          <div class="item"><strong>Sync Runs</strong><div id="syncHistory" class="list"></div></div>
          <div class="item"><strong>Charts</strong><div id="chartsHistory" class="list"></div></div>
          <div class="item"><strong>Errors</strong><div id="errorsHistory" class="list"></div></div>
        </div>
      </div>
    </section>

    <section class="panel" id="settingsPanel">
      <div class="card">
        <h2>Settings</h2>
        <div class="grid" id="settingsGrid"></div>
      </div>
    </section>

    <div class="footer">Supreme Zone Platform • Render Web Service • White Dashboard Edition</div>
  </div>

  <script id="app-data" type="application/json">{payload}</script>
  <script>
    const APP = JSON.parse(document.getElementById('app-data').textContent);

    const $ = (id) => document.getElementById(id);
    const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (ch) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
    const fmtZone = (z) => !z ? '<span class="muted">لا توجد</span>' : `
      <div><span class="pill">${{esc(z.side)}}</span><span class="pill">${{esc(z.timeframe)}}</span><span class="pill">${{esc(z.score)}}</span></div>
      <div class="muted">${{esc(z.lower)}} → ${{esc(z.upper)}}</div>
      <div class="mini">${{esc(z.note || '')}}</div>`;
    const fmtObj = (obj) => `<pre>${{esc(JSON.stringify(obj, null, 2))}}</pre>`;

    function setActivePanel(panelId) {{
      document.querySelectorAll('.panel').forEach((p) => p.classList.remove('active'));
      document.getElementById(panelId).classList.add('active');
      document.querySelectorAll('.tab').forEach((tab) => tab.classList.toggle('active', tab.dataset.panel === panelId));
    }}

    document.querySelectorAll('.tab').forEach((tab) => tab.addEventListener('click', () => setActivePanel(tab.dataset.panel)));

    function renderAll() {{
      const snapshot = APP.snapshot || {{}};
      const analysis = snapshot.analysis || {{}};
      const monitoring = snapshot.monitoring || {{}};
      const execution = snapshot.execution || {{}};
      const reports = snapshot.reports || {{}};
      const backtest = snapshot.backtest || {{}};
      const search = snapshot.search || {{}};
      const settings = APP.data_config || {{}};
      const strategies = APP.strategies || {{}};
      const history = APP.history || {{}};

      $('bootReady').textContent = APP.boot?.ready ? 'جاهز' : 'غير جاهز';
      $('activeStrategy').textContent = strategies.active?.name || 'N/A';
      $('activeSource').textContent = settings.source || 'mt5';
      $('activeSymbols').textContent = (settings.symbols || []).join(', ') || 'N/A';
      $('activeTimeframes').textContent = (settings.timeframes || []).join(', ') || 'N/A';

      $('statAnalyzed').textContent = analysis.frame_count || 0;
      $('statOpenPositions').textContent = (execution.results || 0);
      $('statZones').textContent = ((analysis.buy_zone ? 1 : 0) + (analysis.sell_zone ? 1 : 0));
      $('statReports').textContent = reports.artifacts || 0;
      $('statCycles').textContent = monitoring.cycles || 0;
      $('statMonitoring').textContent = monitoring.running ? 1 : 0;

      $('overviewGrid').innerHTML = `
        <div class="stat"><div class="label">آخر توليد</div><div class="value" style="font-size:16px;">${{esc(snapshot.generated_at || '-')}}</div></div>
        <div class="stat"><div class="label">آخر خطأ</div><div class="value" style="font-size:16px;">${{esc(search.last_error || monitoring.last_error || backtest.last_error || 'لا يوجد')}}</div></div>
        <div class="stat"><div class="label">إجمالي الفريمات</div><div class="value">${{analysis.frame_count || 0}}</div></div>
        <div class="stat"><div class="label">نتائج التنفيذ</div><div class="value">${{execution.results || 0}}</div></div>
        <div class="stat"><div class="label">عدد الملفات</div><div class="value">${{(reports.files || []).length}}</div></div>
        <div class="stat"><div class="label">الباك تست</div><div class="value">${{backtest.runs || 0}}</div></div>`;

      $('buyZoneBox').innerHTML = fmtZone(analysis.buy_zone);
      $('sellZoneBox').innerHTML = fmtZone(analysis.sell_zone);
      $('analysisFrames').innerHTML = (analysis.frames || []).map((frame) => `<div class="item"><strong>${{esc(frame.timeframe)}} • ${{esc(frame.symbol || '')}}</strong>${{fmtObj(frame)}}</div>`).join('') || '<div class="item">لا توجد تحليلات بعد</div>';

      $('activeStrategyCard').innerHTML = strategies.active ? fmtObj(strategies.active) : '<span class="muted">لا توجد استراتيجية نشطة</span>';
      const historyEntries = Object.entries(strategies.history || {{}});
      $('strategyHistory').innerHTML = historyEntries.length
        ? historyEntries.map(([name, versions]) => `<div class="item"><strong>${{esc(name)}}</strong><div class="mini">الإصدارات: ${{versions.length}}</div>${{versions.map(v => `<div class="pill">${{esc(v.version)}}${{v.active ? ' • active' : ''}}</div>`).join('')}}</div>`).join('')
        : '<div class="item">لا يوجد تاريخ استراتيجيات</div>';

      $('reportCount').textContent = `${{reports.artifacts || 0}} ملف تقرير`;
      $('reportFiles').innerHTML = (reports.files || []).map((f) => `<div class="item">${{esc(f)}}</div>`).join('') || '<div class="item">لا توجد تقارير</div>';

      $('monitorStatus').innerHTML = `
        <div class="pill">${{monitoring.running ? 'Running' : 'Stopped'}}</div>
        <div class="pill">Cycles: ${{monitoring.cycles || 0}}</div>
        <div class="pill">Invalidations: ${{monitoring.invalidations || 0}}</div>
        <div class="pill">Reanalyses: ${{monitoring.reanalyses || 0}}</div>`;
      $('watchlistBox').innerHTML = (monitoring.watchlist || []).map((item) => `<div class="item"><strong>${{esc(item.symbol)}}</strong>${{fmtObj(item)}}</div>`).join('') || '<div class="item">لا توجد عناصر مراقبة</div>';

      $('syncHistory').innerHTML = (history.sync_runs || []).map((row) => `<div class="item"><strong>${{esc(row.symbol)}} • ${{esc(row.timeframe)}}</strong><div class="mini">${{esc(row.status)}} • ${{esc(row.bars)}} bars • ${{esc(row.created_at)}}</div></div>`).join('') || '<div class="item">لا توجد عمليات مزامنة</div>';
      $('chartsHistory').innerHTML = (history.charts || []).map((row) => `<div class="item"><strong>${{esc(row.symbol)}} • ${{esc(row.timeframe)}}</strong><div class="mini">${{esc(row.chart_path)}}</div></div>`).join('') || '<div class="item">لا توجد شارتات</div>';
      $('errorsHistory').innerHTML = (history.errors || []).map((row) => `<div class="item"><strong>${{esc(row.context)}}</strong><div class="mini">${{esc(row.message)}}</div></div>`).join('') || '<div class="item">لا توجد أخطاء</div>';

      $('settingsGrid').innerHTML = `
        <div class="stat"><div class="label">مصدر البيانات</div><div class="value" style="font-size:18px;">${{esc(settings.source || 'mt5')}}</div></div>
        <div class="stat"><div class="label">الأزواج</div><div class="value" style="font-size:18px;">${{(settings.symbols || []).length}}</div></div>
        <div class="stat"><div class="label">الفريمات</div><div class="value" style="font-size:18px;">${{(settings.timeframes || []).length}}</div></div>
        <div class="stat"><div class="label">الشموع</div><div class="value" style="font-size:18px;">${{settings.bars || 500}}</div></div>
        <div class="stat"><div class="label">API Key</div><div class="value" style="font-size:18px;">${{settings.api_key_present ? 'Present' : 'Missing'}}</div></div>
        <div class="stat"><div class="label">Base URL</div><div class="value" style="font-size:18px;">${{esc(settings.base_url || '')}}</div></div>`;
    }}

    async function postJson(url, body) {{
      const response = await fetch(url, {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify(body),
      }});
      if (!response.ok) throw new Error(await response.text());
      return response.json();
    }}

    document.getElementById('strategyForm').addEventListener('submit', async (event) => {{
      event.preventDefault();
      const fileInput = document.getElementById('strategyFile');
      const file = fileInput.files[0];
      if (!file) return;
      const formData = new FormData();
      formData.append('file', file);
      formData.append('activate', document.getElementById('activateStrategy').value);
      const response = await fetch('/api/strategies/upload', {{ method: 'POST', body: formData }});
      if (!response.ok) alert('فشل رفع الاستراتيجية'); else window.location.reload();
    }});

    document.getElementById('deactivateStrategyBtn').addEventListener('click', async () => {{
      const response = await fetch('/api/strategies/deactivate', {{ method: 'POST' }});
      if (!response.ok) alert('فشل إيقاف الاستراتيجية'); else window.location.reload();
    }});

    document.getElementById('dataForm').addEventListener('submit', async (event) => {{
      event.preventDefault();
      const payload = {{
        source: document.getElementById('dataSource').value,
        symbols: document.getElementById('symbolsInput').value,
        timeframes: document.getElementById('timeframesInput').value,
        bars: Number(document.getElementById('barsInput').value || 500),
        api_key: document.getElementById('apiKeyInput').value,
        base_url: document.getElementById('baseUrlInput').value,
      }};
      const response = await postJson('/api/data/config', payload);
      if (!response.ok) alert('فشل حفظ البيانات'); else window.location.reload();
    }});

    document.getElementById('runBtn').addEventListener('click', async () => {{
      const response = await fetch('/api/run', {{ method: 'POST' }});
      if (!response.ok) alert('فشل التشغيل'); else window.location.reload();
    }});

    document.getElementById('syncBtn').addEventListener('click', async () => {{
      const response = await fetch('/api/data/sync', {{ method: 'POST' }});
      if (!response.ok) alert('فشل جلب البيانات'); else window.location.reload();
    }});

    document.getElementById('syncNowBtn').addEventListener('click', async () => {{
      const response = await fetch('/api/data/sync', {{ method: 'POST' }});
      if (!response.ok) alert('فشل جلب البيانات'); else window.location.reload();
    }});

    document.getElementById('startMonBtn').addEventListener('click', async () => {{
      const response = await fetch('/api/monitoring/start', {{ method: 'POST' }});
      if (!response.ok) alert('فشل بدء المراقبة'); else window.location.reload();
    }});

    document.getElementById('stopMonBtn').addEventListener('click', async () => {{
      const response = await fetch('/api/monitoring/stop', {{ method: 'POST' }});
      if (!response.ok) alert('فشل إيقاف المراقبة'); else window.location.reload();
    }});

    document.getElementById('refreshBtn').addEventListener('click', () => window.location.reload());

    renderAll();
  </script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
    return RedirectResponse(url="/dashboard", status_code=307)


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard() -> HTMLResponse:
    try:
        platform = _get_platform()
        snapshot = platform.dashboard_service.snapshot(
            analysis_engine=platform.analysis_engine,
            search_engine=platform.search_engine,
            monitoring_engine=platform.monitoring_engine,
            execution_engine=platform.execution_engine,
            report_engine=platform.report_engine,
            backtest_engine=platform.backtest_engine,
        )
        return HTMLResponse(
            content=_render_dashboard_html(snapshot, _strategies_payload(), _data_config_payload(), _history_payload()),
        )
    except Exception as exc:
        return HTMLResponse(
            content=f"""<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1'><title>Supreme Zone Platform</title><style>body{{font-family:system-ui;background:#f8fafc;color:#0f172a;padding:24px}}.card{{max-width:900px;margin:0 auto;background:#fff;border:1px solid #dbe4f0;border-radius:20px;padding:20px;box-shadow:0 16px 40px rgba(15,23,42,.08)}}pre{{white-space:pre-wrap;word-break:break-word;background:#f1f5f9;padding:16px;border-radius:14px}}</style></head><body><div class='card'><h1>Supreme Zone Platform</h1><p>Dashboard fallback is active because the live page hit an error.</p><pre>{escape(str(exc))}</pre><p>Open /healthz for a quick status check.</p></div></body></html>""",
            status_code=200,
        )


@app.get("/healthz")
async def healthz() -> dict[str, Any]:
    bootstrap_result = getattr(app.state, "bootstrap_result", None)
    platform = getattr(app.state, "platform", None)
    return {
        "status": "ok",
        "app_name": getattr(bootstrap_result, "app_name", "Supreme Zone Platform"),
        "ready": bool(getattr(bootstrap_result, "ready", False)),
        "platform_ready": isinstance(platform, SupremeZonePlatform),
    }


@app.get("/api/status")
async def api_status() -> dict[str, Any]:
    platform = _get_platform()
    snapshot = platform.dashboard_service.snapshot(
        analysis_engine=platform.analysis_engine,
        search_engine=platform.search_engine,
        monitoring_engine=platform.monitoring_engine,
        execution_engine=platform.execution_engine,
        report_engine=platform.report_engine,
        backtest_engine=platform.backtest_engine,
    )
    return {
        "bootstrap": _bootstrap_payload(),
        "platform": {
            "cycles": platform.state.cycles,
            "last_error": platform.state.last_error,
            "last_dashboard": str(platform.state.last_dashboard) if platform.state.last_dashboard else None,
        },
        "dashboard": snapshot,
        "strategies": _strategies_payload(),
        "data_config": _data_config_payload(),
        "history": _history_payload(),
    }


@app.get("/api/dashboard")
async def api_dashboard() -> dict[str, Any]:
    platform = _get_platform()
    return platform.dashboard_service.snapshot(
        analysis_engine=platform.analysis_engine,
        search_engine=platform.search_engine,
        monitoring_engine=platform.monitoring_engine,
        execution_engine=platform.execution_engine,
        report_engine=platform.report_engine,
        backtest_engine=platform.backtest_engine,
    )


@app.get("/api/strategies")
async def api_strategies() -> dict[str, Any]:
    return _strategies_payload()


@app.post("/api/strategies/upload")
async def api_strategy_upload(file: UploadFile = File(...), activate: str = Form("true")) -> dict[str, Any]:
    platform = _get_platform()
    strategy_dir = Path(platform.data_engine.settings.strategy.directory)
    strategy_dir.mkdir(parents=True, exist_ok=True)
    original_name = Path(file.filename or "strategy.yaml")
    suffix = original_name.suffix or ".yaml"
    stem = original_name.stem or "strategy"
    target = strategy_dir / f"{stem}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}{suffix}"
    content = await file.read()
    target.write_bytes(content)
    strategy = platform.analysis_engine.strategy_manager.add_strategy_file(target)
    if activate.lower() == "true":
        platform.analysis_engine.strategy_manager.activate_strategy(strategy.name)
    return {"ok": True, "strategy": _strategy_payload(strategy), "strategies": _strategies_payload()}


@app.post("/api/strategies/activate/{name}")
async def api_strategy_activate(name: str) -> dict[str, Any]:
    platform = _get_platform()
    strategy = platform.analysis_engine.strategy_manager.activate_strategy(name)
    return {"ok": True, "strategy": _strategy_payload(strategy), "strategies": _strategies_payload()}


@app.post("/api/strategies/deactivate")
async def api_strategy_deactivate() -> dict[str, Any]:
    platform = _get_platform()
    platform.analysis_engine.strategy_manager.deactivate_strategy()
    return {"ok": True, "strategies": _strategies_payload()}


@app.post("/api/data/config")
async def api_data_config(request: Request) -> dict[str, Any]:
    platform = _get_platform()
    payload = await request.json()
    source = str(payload.get("source", "mt5"))
    symbols = str(payload.get("symbols", ""))
    timeframes = str(payload.get("timeframes", ""))
    bars = int(payload.get("bars", 500) or 500)
    api_key = payload.get("api_key")
    base_url = payload.get("base_url")
    parsed_symbols = tuple(item.strip().upper() for item in symbols.split(",") if item.strip())
    parsed_timeframes = tuple(item.strip().upper() for item in timeframes.split(",") if item.strip())
    if parsed_symbols or parsed_timeframes:
        _apply_runtime_market_config(parsed_symbols or tuple(platform.data_engine.symbol_manager.symbols), parsed_timeframes or tuple(platform.data_engine.timeframe_manager.supported), bars)
    if api_key == "***":
        api_key = None
    platform.data_engine.set_data_source(source, api_key=api_key, base_url=base_url)
    app.state.runtime["data_source"] = platform.data_engine.data_source
    app.state.runtime["bars"] = bars
    return {"ok": True, "data_config": _data_config_payload()}


@app.get("/api/data/config")
async def api_data_config_get() -> dict[str, Any]:
    return _data_config_payload()


@app.post("/api/data/sync")
async def api_data_sync(
    bars: int | None = Form(None),
    use_cache: bool = Form(True),
    force_refresh: bool = Form(False),
) -> dict[str, Any]:
    platform = _get_platform()
    results = platform.data_engine.sync_all(bars=bars or app.state.runtime.get("bars"), use_cache=use_cache, force_refresh=force_refresh)
    return {"ok": True, "results": results, "history": _history_payload()}


@app.post("/api/run")
async def api_run() -> dict[str, Any]:
    platform = _get_platform()
    strategy = platform.analysis_engine.strategy_manager.get_active_strategy()
    strategy_path = strategy.source_path if strategy is not None else None
    symbols = app.state.runtime.get("symbols") or None
    bars = app.state.runtime.get("bars") or None
    result = platform.run_once(strategy_path=strategy_path, bars=bars, symbols=symbols)
    return {
        "status": "ok",
        "symbols": list(result.symbols),
        "dashboard_path": str(result.dashboard_path) if result.dashboard_path else None,
        "dashboard_json": str(result.dashboard_json) if result.dashboard_json else None,
        "report_count": len(result.report_artifacts),
        "execution_count": len(result.executions),
        "backtest_count": len(result.backtest_results),
    }


@app.post("/api/monitoring/start")
async def api_monitoring_start() -> dict[str, Any]:
    platform = _get_platform()
    platform.monitoring_engine.start()
    return {"ok": True, "monitoring": platform.dashboard_service.snapshot(
        analysis_engine=platform.analysis_engine,
        search_engine=platform.search_engine,
        monitoring_engine=platform.monitoring_engine,
        execution_engine=platform.execution_engine,
        report_engine=platform.report_engine,
        backtest_engine=platform.backtest_engine,
    )["monitoring"]}


@app.post("/api/monitoring/stop")
async def api_monitoring_stop() -> dict[str, Any]:
    platform = _get_platform()
    platform.monitoring_engine.stop()
    return {"ok": True, "monitoring": platform.dashboard_service.snapshot(
        analysis_engine=platform.analysis_engine,
        search_engine=platform.search_engine,
        monitoring_engine=platform.monitoring_engine,
        execution_engine=platform.execution_engine,
        report_engine=platform.report_engine,
        backtest_engine=platform.backtest_engine,
    )["monitoring"]}


@app.post("/api/monitoring/cycle")
async def api_monitoring_cycle() -> dict[str, Any]:
    platform = _get_platform()
    refreshed = platform.monitoring_engine.run_cycle()
    return {"ok": True, "watchlist": [item.symbol for item in refreshed], "monitoring": platform.dashboard_service.snapshot(
        analysis_engine=platform.analysis_engine,
        search_engine=platform.search_engine,
        monitoring_engine=platform.monitoring_engine,
        execution_engine=platform.execution_engine,
        report_engine=platform.report_engine,
        backtest_engine=platform.backtest_engine,
    )["monitoring"]}


@app.get("/api/history")
async def api_history() -> dict[str, Any]:
    return _history_payload()


@app.get("/api/settings")
async def api_settings() -> dict[str, Any]:
    return {
        "bootstrap": _bootstrap_payload(),
        "strategies": _strategies_payload(),
        "data_config": _data_config_payload(),
    }
