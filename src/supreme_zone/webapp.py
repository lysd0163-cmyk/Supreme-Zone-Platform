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
        "api_key_present": bool(getattr(bootstrap_result.platform.data_engine, "twelve_data_api_key", "")),
    }
    yield


app = FastAPI(title="Supreme Zone Platform", version="0.2.0", lifespan=lifespan)


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
    result = getattr(app.state, "bootstrap_result", None)
    if result is None:
        return {}
    return {
        "ready": bool(getattr(result, "ready", False)),
        "app_name": getattr(result, "app_name", "Supreme Zone Platform"),
        "config_path": str(getattr(result, "config_path", "config/default.yaml")),
        "storage_root": str(getattr(result, "storage_root", "storage")),
        "services_registered": list(getattr(result, "services_registered", ())),
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
        _safe_json({
            "snapshot": snapshot,
            "strategies": strategies,
            "data_config": data_config,
            "history": history,
            "boot": _bootstrap_payload(),
        }),
        ensure_ascii=False,
        default=str,
    ).replace("</", "<\\/")

    active_strategy = escape((strategies.get("active") or {}).get("name", "N/A") or "N/A")
    active_source = escape(str(data_config.get("source", "mt5")))
    selected_symbols = escape(", ".join(data_config.get("symbols", [])) or "N/A")
    selected_timeframes = escape(", ".join(data_config.get("timeframes", [])) or "N/A")
    bars = escape(str(data_config.get("bars", 500)))
    api_key_status = "محفوظ" if data_config.get("api_key_present") else "غير محفوظ"
    base_url = escape(str(data_config.get("base_url", "https://api.twelvedata.com/time_series")))

    html = """<!doctype html>
<html lang="ar" dir="rtl">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Supreme Zone Platform</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #07111f;
      --bg-2: #0b1728;
      --surface: rgba(10,18,31,.84);
      --surface-2: rgba(16,24,40,.96);
      --border: rgba(148,163,184,.18);
      --text: #e5eefc;
      --muted: #91a4c4;
      --accent: #6ea8ff;
      --accent-2: #8b5cf6;
      --good: #22c55e;
      --warn: #f59e0b;
      --bad: #ef4444;
      --shadow: 0 30px 80px rgba(0,0,0,.38);
      --radius: 26px;
    }
    * { box-sizing:border-box; }
    html, body {
      margin:0;
      padding:0;
      min-height:100%;
      background:
        radial-gradient(circle at top right, rgba(110,168,255,.24), transparent 28%),
        radial-gradient(circle at top left, rgba(139,92,246,.22), transparent 26%),
        linear-gradient(180deg, var(--bg), var(--bg-2));
      color:var(--text);
      font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    body { min-height:100vh; }
    .shell { max-width: 1680px; margin:0 auto; padding: 18px; }
    .hero {
      position:relative;
      overflow:hidden;
      border:1px solid var(--border);
      background: linear-gradient(180deg, rgba(12,19,33,.94), rgba(7,17,31,.92));
      box-shadow: var(--shadow);
      border-radius: 32px;
      padding: 24px;
    }
    .hero::before {
      content:"";
      position:absolute;
      inset:-80px -160px auto auto;
      width:320px;
      height:320px;
      background: radial-gradient(circle, rgba(110,168,255,.18), transparent 68%);
      filter: blur(10px);
      pointer-events:none;
    }
    .top {
      display:flex;
      justify-content:space-between;
      gap:18px;
      flex-wrap:wrap;
      align-items:flex-start;
      position:relative;
      z-index:1;
    }
    .brand {
      display:flex;
      flex-direction:column;
      gap:10px;
      max-width: 900px;
    }
    .badge {
      display:inline-flex;
      align-items:center;
      gap:8px;
      width:max-content;
      padding:7px 12px;
      border-radius:999px;
      border:1px solid rgba(110,168,255,.22);
      background: rgba(110,168,255,.10);
      color: #cfe2ff;
      font-size:12px;
      letter-spacing:.3px;
    }
    .title {
      font-size: clamp(30px, 4.5vw, 56px);
      line-height:1.02;
      margin:0;
      letter-spacing:-.03em;
    }
    .subtitle {
      color:var(--muted);
      font-size: 15px;
      line-height:1.8;
      max-width: 920px;
    }
    .hero-actions {
      display:flex;
      flex-direction:column;
      align-items:flex-start;
      gap:12px;
      min-width: 320px;
    }
    .toolbar {
      display:flex;
      flex-wrap:wrap;
      gap:10px;
    }
    .btn {
      appearance:none;
      border:1px solid var(--border);
      background: rgba(255,255,255,.03);
      color:var(--text);
      border-radius: 16px;
      padding: 12px 16px;
      font-weight:700;
      cursor:pointer;
      transition: transform .15s ease, border-color .15s ease, background .15s ease;
      box-shadow: 0 8px 24px rgba(0,0,0,.18);
    }
    .btn:hover { transform: translateY(-1px); border-color: rgba(110,168,255,.45); }
    .btn.primary {
      background: linear-gradient(135deg, var(--accent), var(--accent-2));
      border-color: transparent;
      color: #fff;
    }
    .btn.ghost {
      background: rgba(255,255,255,.02);
    }
    .status-row {
      display:flex;
      flex-wrap:wrap;
      gap:10px;
      margin-top: 14px;
    }
    .chip {
      display:inline-flex;
      align-items:center;
      gap:8px;
      padding:10px 14px;
      border-radius:999px;
      border:1px solid var(--border);
      background: rgba(255,255,255,.03);
      color:var(--text);
      font-size:13px;
      backdrop-filter: blur(10px);
    }
    .chip strong { font-size:14px; }
    .grid-kpi {
      display:grid;
      grid-template-columns: repeat(6, minmax(0, 1fr));
      gap:14px;
      margin-top:18px;
    }
    .kpi {
      border:1px solid var(--border);
      background: rgba(255,255,255,.03);
      border-radius: 22px;
      padding: 16px;
      box-shadow: var(--shadow);
      min-height: 96px;
    }
    .kpi .label { color: var(--muted); font-size: 12px; margin-bottom: 10px; }
    .kpi .value { font-size: clamp(20px, 2vw, 30px); font-weight: 900; letter-spacing: -.03em; }
    .tabs {
      display:flex;
      gap:10px;
      flex-wrap:wrap;
      margin: 18px 0;
    }
    .tab {
      padding: 11px 16px;
      border-radius: 999px;
      border:1px solid var(--border);
      background: rgba(255,255,255,.03);
      color: var(--text);
      cursor:pointer;
      font-weight:800;
    }
    .tab.active {
      background: linear-gradient(135deg, rgba(110,168,255,.95), rgba(139,92,246,.95));
      border-color: transparent;
      color:#fff;
    }
    .panel { display:none; }
    .panel.active { display:block; }
    .card {
      border:1px solid var(--border);
      background: var(--surface);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
      padding: 18px;
      backdrop-filter: blur(14px);
    }
    .card + .card { margin-top:18px; }
    .card-head {
      display:flex;
      justify-content:space-between;
      gap:12px;
      align-items:flex-start;
      flex-wrap:wrap;
      margin-bottom: 14px;
    }
    h2 {
      margin:0;
      font-size: 20px;
      letter-spacing:-.02em;
    }
    .hint { color: var(--muted); font-size: 13px; line-height:1.8; }
    .grid {
      display:grid;
      gap:14px;
      grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
    }
    .field-grid {
      display:grid;
      gap:12px;
      grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
    }
    label {
      display:block;
      font-size: 12px;
      color: var(--muted);
      margin-bottom: 8px;
    }
    input, select, textarea {
      width:100%;
      padding: 13px 14px;
      border-radius: 15px;
      border:1px solid var(--border);
      background: rgba(8,14,24,.88);
      color: var(--text);
      outline:none;
    }
    input:focus, select:focus, textarea:focus {
      border-color: rgba(110,168,255,.5);
      box-shadow: 0 0 0 4px rgba(110,168,255,.12);
    }
    .item {
      border:1px solid var(--border);
      background: rgba(255,255,255,.03);
      border-radius: 20px;
      padding: 14px;
    }
    .item strong { display:block; margin-bottom:8px; }
    .list {
      display:grid;
      gap:12px;
    }
    .pill {
      display:inline-flex;
      align-items:center;
      gap:6px;
      padding: 5px 10px;
      border-radius:999px;
      background: rgba(110,168,255,.12);
      color: #cfe2ff;
      font-size:12px;
      margin-inline-end:6px;
      margin-bottom:6px;
      border:1px solid rgba(110,168,255,.22);
    }
    .pill.good { background: rgba(34,197,94,.12); color:#b8f3cd; border-color: rgba(34,197,94,.22); }
    .pill.warn { background: rgba(245,158,11,.12); color:#fde2b1; border-color: rgba(245,158,11,.22); }
    .pill.bad { background: rgba(239,68,68,.12); color:#fecaca; border-color: rgba(239,68,68,.22); }
    .muted { color: var(--muted); }
    .mini { font-size:12px; color:var(--muted); line-height:1.65; }
    .table {
      width:100%;
      border-collapse:collapse;
      overflow:hidden;
      border-radius:18px;
      border:1px solid var(--border);
    }
    .table th, .table td {
      padding: 12px 10px;
      border-bottom:1px solid rgba(148,163,184,.12);
      text-align:right;
      font-size: 13px;
    }
    .table th {
      color: var(--muted);
      font-size:12px;
      font-weight:700;
      background: rgba(255,255,255,.02);
    }
    .table tr:last-child td { border-bottom:none; }
    .footer {
      color: var(--muted);
      text-align:center;
      font-size:12px;
      padding: 18px 0 8px;
    }
    .two-col {
      display:grid;
      gap:14px;
      grid-template-columns: 1.2fr .8fr;
    }
    @media (max-width: 1100px) {
      .grid-kpi { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .two-col { grid-template-columns: 1fr; }
      .hero-actions { width:100%; min-width:0; }
    }
    @media (max-width: 640px) {
      .shell { padding:12px; }
      .hero { padding:18px; border-radius:24px; }
      .grid-kpi { grid-template-columns: 1fr 1fr; }
      .toolbar { width:100%; }
      .btn { flex:1 1 auto; }
    }
  </style>
</head>
<body>
  <div class="shell">
    <section class="hero">
      <div class="top">
        <div class="brand">
          <span class="badge">Supreme Zone Platform • Live Control Center</span>
          <h1 class="title">منصة تحليل مؤسسي بواجهة احترافية وسريعة</h1>
          <div class="subtitle">
            مركز أوامر وتحكم لإدارة الاستراتيجيات، مزامنة البيانات، ومراقبة الزونات والنتائج مع واجهة حديثة أوضح وأكثر نظافة.
          </div>
          <div class="status-row">
            <span class="chip">الحالة: <strong id="bootReady">جاهز</strong></span>
            <span class="chip">الاستراتيجية: <strong id="activeStrategy">__ACTIVE_STRATEGY__</strong></span>
            <span class="chip">المصدر: <strong id="activeSource">__SOURCE__</strong></span>
            <span class="chip">الأزواج: <strong id="activeSymbols">__SYMBOLS__</strong></span>
            <span class="chip">الفريمات: <strong id="activeTimeframes">__TIMEFRAMES__</strong></span>
          </div>
        </div>
        <div class="hero-actions">
          <div class="toolbar">
            <button class="btn primary" id="runBtn">Run / Analyze</button>
            <button class="btn" id="syncBtn">Sync Data</button>
            <button class="btn" id="startMonBtn">Start Monitor</button>
            <button class="btn" id="stopMonBtn">Stop Monitor</button>
            <button class="btn ghost" id="refreshBtn">Refresh</button>
          </div>
          <div class="mini">إذا البيانات ناقصة، سيظهر السبب بدل فشل صامت.</div>
        </div>
      </div>

      <div class="grid-kpi">
        <div class="kpi"><div class="label">الأزواج المحللة</div><div class="value" id="statAnalyzed">0</div></div>
        <div class="kpi"><div class="label">الصفقات المفتوحة</div><div class="value" id="statOpenPositions">0</div></div>
        <div class="kpi"><div class="label">الزونات النشطة</div><div class="value" id="statZones">0</div></div>
        <div class="kpi"><div class="label">التقارير</div><div class="value" id="statReports">0</div></div>
        <div class="kpi"><div class="label">الدورات</div><div class="value" id="statCycles">0</div></div>
        <div class="kpi"><div class="label">المراقبة</div><div class="value" id="statMonitoring">0</div></div>
      </div>
    </section>

    <div class="tabs">
      <button class="tab active" data-panel="overviewPanel">Overview</button>
      <button class="tab" data-panel="strategyPanel">Strategy</button>
      <button class="tab" data-panel="dataPanel">Data Center</button>
      <button class="tab" data-panel="analysisPanel">Analysis</button>
      <button class="tab" data-panel="reportsPanel">Reports</button>
      <button class="tab" data-panel="monitoringPanel">Monitoring</button>
      <button class="tab" data-panel="historyPanel">History</button>
      <button class="tab" data-panel="settingsPanel">Settings</button>
    </div>

    <section class="panel active" id="overviewPanel">
      <div class="two-col">
        <div class="card">
          <div class="card-head">
            <div>
              <h2>Overview</h2>
              <div class="hint">ملخص سريع للحالة الحالية والآخر خطأ ونقطة البدء.</div>
            </div>
          </div>
          <div class="grid" id="overviewGrid"></div>
        </div>
        <div class="card">
          <div class="card-head">
            <div>
              <h2>Live Signal</h2>
              <div class="hint">أقرب معلومات تشغيلية مباشرة من الـ snapshot.</div>
            </div>
          </div>
          <div class="list">
            <div class="item"><strong>آخر توليد</strong><div id="lastGenerated" class="mini">-</div></div>
            <div class="item"><strong>آخر خطأ</strong><div id="lastError" class="mini">-</div></div>
            <div class="item"><strong>التحليل الحالي</strong><div id="currentAnalysis" class="mini">-</div></div>
          </div>
        </div>
      </div>
    </section>

    <section class="panel" id="strategyPanel">
      <div class="card">
        <div class="card-head">
          <div>
            <h2>Strategy Manager</h2>
            <div class="hint">رفع ملف استراتيجية وتفعيلها أو إبقاؤها محفوظة فقط.</div>
          </div>
        </div>
        <form id="strategyForm" class="field-grid">
          <div><label>ملف الاستراتيجية (PDF / JSON / TXT / MD / YAML)</label><input type="file" id="strategyFile" accept=".pdf,.json,.txt,.md,.yaml,.yml" required /></div>
          <div><label>السلوك بعد الرفع</label><select id="activateStrategy"><option value="true">تفعيلها مباشرة</option><option value="false">حفظ فقط</option></select></div>
          <div style="grid-column:1/-1; display:flex; gap:10px; flex-wrap:wrap; align-items:center;">
            <button class="btn primary" type="submit">Upload Strategy</button>
            <button class="btn" type="button" id="deactivateStrategyBtn">Deactivate Active</button>
          </div>
        </form>
        <div class="two-col" style="margin-top:18px;">
          <div class="item"><strong>الاستراتيجية النشطة</strong><div id="activeStrategyCard" class="mini"></div></div>
          <div class="item"><strong>الإصدارات</strong><div id="strategyHistory" class="list"></div></div>
        </div>
      </div>
    </section>

    <section class="panel" id="dataPanel">
      <div class="card">
        <div class="card-head">
          <div>
            <h2>Data Center</h2>
            <div class="hint">اختر مصدر البيانات، الأزواج، الفريمات، وعدد الشموع المطلوب.</div>
          </div>
        </div>
        <form id="dataForm" class="field-grid">
          <div><label>مصدر البيانات</label><select id="dataSource"><option value="twelve_data">Twelve Data</option><option value="mt5">MT5</option></select></div>
          <div><label>عدد الشموع</label><input id="barsInput" type="number" min="50" step="1" value="__BARS__" /></div>
          <div><label>الأزواج</label><input id="symbolsInput" type="text" value="__SYMBOLS__" placeholder="EURUSD,GBPUSD,XAUUSD" /></div>
          <div><label>الفريمات</label><input id="timeframesInput" type="text" value="__TIMEFRAMES__" placeholder="D1,H4,H1,M15" /></div>
          <div><label>Twelve Data API Key</label><input id="apiKeyInput" type="password" value="" placeholder="مفتاح محفوظ" /></div>
          <div><label>Base URL</label><input id="baseUrlInput" type="text" value="__BASE_URL__" /></div>
          <div style="grid-column:1/-1; display:flex; gap:10px; flex-wrap:wrap; align-items:center;">
            <span class="pill" id="apiKeyBadge">__API_KEY_STATE__</span>
            <button class="btn primary" type="submit">Save Data Settings</button>
            <button class="btn" type="button" id="syncNowBtn">Sync Now</button>
          </div>
        </form>
      </div>
    </section>

    <section class="panel" id="analysisPanel">
      <div class="card">
        <div class="card-head">
          <div>
            <h2>Analysis</h2>
            <div class="hint">BUY ZONE و SELL ZONE مع تفاصيل الإطار الزمني.</div>
          </div>
        </div>
        <div class="grid">
          <div class="item"><strong>BUY ZONE</strong><div id="buyZoneBox"></div></div>
          <div class="item"><strong>SELL ZONE</strong><div id="sellZoneBox"></div></div>
        </div>
        <div class="list" style="margin-top:14px;" id="analysisFrames"></div>
      </div>
    </section>

    <section class="panel" id="reportsPanel">
      <div class="card">
        <div class="card-head">
          <div>
            <h2>Reports</h2>
            <div class="hint">ملفات التقارير والنواتج الأخيرة.</div>
          </div>
        </div>
        <div class="grid">
          <div class="item"><strong>آخر التقارير</strong><div id="reportCount"></div></div>
          <div class="item"><strong>الملفات</strong><div id="reportFiles" class="list"></div></div>
        </div>
      </div>
    </section>

    <section class="panel" id="monitoringPanel">
      <div class="card">
        <div class="card-head">
          <div>
            <h2>Monitoring</h2>
            <div class="hint">تشغيل وإيقاف المراقبة وعرض عناصر المتابعة.</div>
          </div>
        </div>
        <div class="grid">
          <div class="item"><strong>الحالة</strong><div id="monitorStatus"></div></div>
          <div class="item"><strong>Watchlist</strong><div id="watchlistBox" class="list"></div></div>
        </div>
      </div>
    </section>

    <section class="panel" id="historyPanel">
      <div class="card">
        <div class="card-head">
          <div>
            <h2>History</h2>
            <div class="hint">سجل المزامنة، الشارتات، والأخطاء.</div>
          </div>
        </div>
        <div class="grid">
          <div class="item"><strong>Sync Runs</strong><div id="syncHistory" class="list"></div></div>
          <div class="item"><strong>Charts</strong><div id="chartsHistory" class="list"></div></div>
          <div class="item"><strong>Errors</strong><div id="errorsHistory" class="list"></div></div>
        </div>
      </div>
    </section>

    <section class="panel" id="settingsPanel">
      <div class="card">
        <div class="card-head">
          <div>
            <h2>Settings</h2>
            <div class="hint">ملخص الإعدادات الحالية ونقاط الربط الأساسية.</div>
          </div>
        </div>
        <div class="grid" id="settingsGrid"></div>
      </div>
    </section>

    <div class="footer">Supreme Zone Platform • modern dashboard build • RTL support</div>
  </div>

  <script id="app-data" type="application/json">__PAYLOAD__</script>
  <script>
    const APP = JSON.parse(document.getElementById('app-data').textContent);
    const $ = (id) => document.getElementById(id);
    const esc = (value) => String(value ?? '').replace(/[&<>\"]'/g, (ch) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
    const fmtZone = (z) => !z
      ? '<span class="muted">لا توجد</span>'
      : `<div><span class="pill">${esc(z.side)}</span><span class="pill">${esc(z.timeframe)}</span><span class="pill">${esc(z.score)}</span></div><div class="mini">${esc(z.lower)} → ${esc(z.upper)}</div><div class="mini">${esc(z.note || '')}</div>`;
    const fmtObj = (obj) => `<pre>${esc(JSON.stringify(obj, null, 2))}</pre>`;

    function setActivePanel(panelId) {
      document.querySelectorAll('.panel').forEach((p) => p.classList.remove('active'));
      document.getElementById(panelId).classList.add('active');
      document.querySelectorAll('.tab').forEach((tab) => tab.classList.toggle('active', tab.dataset.panel === panelId));
    }

    document.querySelectorAll('.tab').forEach((tab) => tab.addEventListener('click', () => setActivePanel(tab.dataset.panel)));

    function renderAll() {
      const snapshot = APP.snapshot || {};
      const analysis = snapshot.analysis || {};
      const monitoring = snapshot.monitoring || {};
      const execution = snapshot.execution || {};
      const reports = snapshot.reports || {};
      const backtest = snapshot.backtest || {};
      const search = snapshot.search || {};
      const settings = APP.data_config || {};
      const strategies = APP.strategies || {};
      const history = APP.history || {}; 

      $('bootReady').textContent = APP.boot?.ready ? 'جاهز' : 'غير جاهز';
      $('activeStrategy').textContent = strategies.active?.name || 'N/A';
      $('activeSource').textContent = settings.source || 'mt5';
      $('activeSymbols').textContent = (settings.symbols || []).join(', ') || 'N/A';
      $('activeTimeframes').textContent = (settings.timeframes || []).join(', ') || 'N/A';

      $('statAnalyzed').textContent = analysis.frame_count || 0;
      $('statOpenPositions').textContent = execution.results || 0;
      $('statZones').textContent = ((analysis.buy_zone ? 1 : 0) + (analysis.sell_zone ? 1 : 0));
      $('statReports').textContent = reports.artifacts || 0;
      $('statCycles').textContent = monitoring.cycles || 0;
      $('statMonitoring').textContent = monitoring.running ? 1 : 0;

      $('overviewGrid').innerHTML = [
        ['آخر توليد', snapshot.generated_at || '-'],
        ['آخر خطأ', search.last_error || monitoring.last_error || backtest.last_error || 'لا يوجد'],
        ['إجمالي الفريمات', analysis.frame_count || 0],
        ['نتائج التنفيذ', execution.results || 0],
        ['عدد الملفات', (reports.files || []).length],
        ['الباك تست', backtest.runs || 0],
      ].map((item) => `<div class="item"><div class="mini">${esc(item[0])}</div><div style="font-size:20px;font-weight:900;margin-top:6px;">${esc(String(item[1]))}</div></div>`).join('');

      $('lastGenerated').textContent = snapshot.generated_at || '-';
      $('lastError').textContent = search.last_error || monitoring.last_error || backtest.last_error || 'لا يوجد';
      $('currentAnalysis').textContent = `${analysis.symbol || 'N/A'} • ${analysis.strategy_name || 'N/A'}`;

      $('buyZoneBox').innerHTML = fmtZone(analysis.buy_zone);
      $('sellZoneBox').innerHTML = fmtZone(analysis.sell_zone);
      $('analysisFrames').innerHTML = (analysis.frames || []).map((frame) => `<div class="item"><strong>${esc(frame.timeframe)} • ${esc(frame.symbol || '')}</strong>${fmtObj(frame)}</div>`).join('') || '<div class="item">لا توجد تحليلات بعد</div>';

      $('activeStrategyCard').innerHTML = strategies.active ? fmtObj(strategies.active) : '<span class="muted">لا توجد استراتيجية نشطة</span>';
      const historyEntries = Object.entries(strategies.history || {});
      $('strategyHistory').innerHTML = historyEntries.length
        ? historyEntries.map(([name, versions]) => `<div class="item"><strong>${esc(name)}</strong><div class="mini">الإصدارات: ${versions.length}</div>${versions.map((v) => `<div class="pill">${esc(v.version)}${v.active ? ' • active' : ''}</div>`).join('')}</div>`).join('')
        : '<div class="item">لا يوجد تاريخ استراتيجيات</div>';

      $('reportCount').textContent = `${reports.artifacts || 0} ملف تقرير`;
      $('reportFiles').innerHTML = (reports.files || []).map((file) => `<div class="item">${esc(file)}</div>`).join('') || '<div class="item">لا توجد تقارير</div>';

      $('monitorStatus').innerHTML = `<div class="pill ${monitoring.running ? 'good' : 'warn'}">${monitoring.running ? 'Running' : 'Stopped'}</div><div class="pill">Cycles: ${monitoring.cycles || 0}</div><div class="pill">Invalidations: ${monitoring.invalidations || 0}</div><div class="pill">Reanalyses: ${monitoring.reanalyses || 0}</div>`;
      $('watchlistBox').innerHTML = (monitoring.watchlist || []).map((item) => `<div class="item"><strong>${esc(item.symbol)}</strong>${fmtObj(item)}</div>`).join('') || '<div class="item">لا توجد عناصر مراقبة</div>';

      $('syncHistory').innerHTML = (history.sync_runs || []).map((row) => `<div class="item"><strong>${esc(row.symbol)} • ${esc(row.timeframe)}</strong><div class="mini">${esc(row.status)} • ${esc(row.bars)} bars • ${esc(row.created_at)}</div></div>`).join('') || '<div class="item">لا توجد عمليات مزامنة</div>';
      $('chartsHistory').innerHTML = (history.charts || []).map((row) => `<div class="item"><strong>${esc(row.symbol)} • ${esc(row.timeframe)}</strong><div class="mini">${esc(row.chart_path)}</div></div>`).join('') || '<div class="item">لا توجد شارتات</div>';
      $('errorsHistory').innerHTML = (history.errors || []).map((row) => `<div class="item"><strong>${esc(row.context)}</strong><div class="mini">${esc(row.message)}</div></div>`).join('') || '<div class="item">لا توجد أخطاء</div>';

      $('settingsGrid').innerHTML = [
        ['مصدر البيانات', settings.source || 'mt5'],
        ['الأزواج', (settings.symbols || []).length],
        ['الفريمات', (settings.timeframes || []).length],
        ['الشموع', settings.bars || 500],
        ['API Key', settings.api_key_present ? 'Present' : 'Missing'],
        ['Base URL', settings.base_url || ''],
        ['MT5', settings.mt5_enabled ? 'Enabled' : 'Disabled'],
      ].map((item) => `<div class="item"><div class="mini">${esc(item[0])}</div><div style="font-size:18px;font-weight:800;margin-top:6px;">${esc(String(item[1]))}</div></div>`).join('');

      $('apiKeyBadge').textContent = settings.api_key_present ? 'API Key محفوظ' : 'API Key غير محفوظ';
      $('apiKeyBadge').className = `pill ${settings.api_key_present ? 'good' : 'warn'}`;
      $('apiKeyInput').value = '';
      $('baseUrlInput').value = settings.base_url || '';
      $('barsInput').value = String(settings.bars || 500);
      $('symbolsInput').value = (settings.symbols || []).join(',');
      $('timeframesInput').value = (settings.timeframes || []).join(',');
      $('dataSource').value = settings.source || 'mt5';
    }

    async function postJson(url, body) {
      const response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!response.ok) throw new Error(await response.text());
      return response.json();
    }

    document.getElementById('strategyForm').addEventListener('submit', async (event) => {
      event.preventDefault();
      const file = document.getElementById('strategyFile').files[0];
      if (!file) return;
      const formData = new FormData();
      formData.append('file', file);
      formData.append('activate', document.getElementById('activateStrategy').value);
      const response = await fetch('/api/strategies/upload', { method: 'POST', body: formData });
      if (!response.ok) alert('فشل رفع الاستراتيجية'); else window.location.reload();
    });

    document.getElementById('deactivateStrategyBtn').addEventListener('click', async () => {
      const response = await fetch('/api/strategies/deactivate', { method: 'POST' });
      if (!response.ok) alert('فشل إيقاف الاستراتيجية'); else window.location.reload();
    });

    document.getElementById('dataForm').addEventListener('submit', async (event) => {
      event.preventDefault();
      const payload = {
        source: document.getElementById('dataSource').value,
        symbols: document.getElementById('symbolsInput').value,
        timeframes: document.getElementById('timeframesInput').value,
        bars: Number(document.getElementById('barsInput').value || 500),
        api_key: document.getElementById('apiKeyInput').value,
        base_url: document.getElementById('baseUrlInput').value,
      };
      const response = await postJson('/api/data/config', payload);
      if (!response.ok) alert('فشل حفظ البيانات'); else window.location.reload();
    });

    document.getElementById('runBtn').addEventListener('click', async () => {
      const response = await fetch('/api/run', { method: 'POST' });
      if (!response.ok) alert('فشل التشغيل'); else window.location.reload();
    });

    document.getElementById('syncBtn').addEventListener('click', async () => {
      const response = await fetch('/api/data/sync', { method: 'POST' });
      if (!response.ok) alert('فشل جلب البيانات'); else window.location.reload();
    });

    document.getElementById('syncNowBtn').addEventListener('click', async () => {
      const response = await fetch('/api/data/sync', { method: 'POST' });
      if (!response.ok) alert('فشل جلب البيانات'); else window.location.reload();
    });

    document.getElementById('startMonBtn').addEventListener('click', async () => {
      const response = await fetch('/api/monitoring/start', { method: 'POST' });
      if (!response.ok) alert('فشل بدء المراقبة'); else window.location.reload();
    });

    document.getElementById('stopMonBtn').addEventListener('click', async () => {
      const response = await fetch('/api/monitoring/stop', { method: 'POST' });
      if (!response.ok) alert('فشل إيقاف المراقبة'); else window.location.reload();
    });

    document.getElementById('refreshBtn').addEventListener('click', () => window.location.reload());
    renderAll();
  </script>
</body>
</html>"""
    return (
        html.replace("__PAYLOAD__", payload)
        .replace("__ACTIVE_STRATEGY__", active_strategy)
        .replace("__SOURCE__", active_source)
        .replace("__SYMBOLS__", selected_symbols)
        .replace("__TIMEFRAMES__", selected_timeframes)
        .replace("__BARS__", bars)
        .replace("__BASE_URL__", base_url)
        .replace("__API_KEY_STATE__", api_key_status)
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
    return RedirectResponse(url="/dashboard", status_code=307)


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard() -> HTMLResponse:
    platform = _get_platform()
    try:
        snapshot = platform.dashboard_service.snapshot(
            analysis_engine=platform.analysis_engine,
            search_engine=platform.search_engine,
            monitoring_engine=platform.monitoring_engine,
            execution_engine=platform.execution_engine,
            report_engine=platform.report_engine,
            backtest_engine=platform.backtest_engine,
        )
        return HTMLResponse(_render_dashboard_html(snapshot, _strategies_payload(), _data_config_payload(), _history_payload()))
    except Exception as exc:
        return HTMLResponse(
            """<!doctype html><html lang='ar' dir='rtl'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1'><title>Supreme Zone Platform</title><style>body{font-family:system-ui;background:#0b1220;color:#e5eefc;padding:24px}.card{max-width:900px;margin:0 auto;background:#111827;border:1px solid rgba(148,163,184,.18);border-radius:20px;padding:20px;box-shadow:0 30px 80px rgba(0,0,0,.35)}pre{white-space:pre-wrap;word-break:break-word;background:#0f172a;padding:16px;border-radius:14px;border:1px solid rgba(148,163,184,.18)}</style></head><body><div class='card'><h1>Supreme Zone Platform</h1><p>Dashboard fallback is active because the live page hit an error.</p><pre>"""
            + escape(str(exc))
            + """</pre><p>Open /healthz for a quick status check.</p></div></body></html>""",
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
    target = strategy_dir / (stem + "_" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S") + suffix)
    target.write_bytes(await file.read())
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
    app.state.runtime["api_key_present"] = bool(platform.data_engine.twelve_data_api_key)
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
    monitoring = platform.dashboard_service.snapshot(
        analysis_engine=platform.analysis_engine,
        search_engine=platform.search_engine,
        monitoring_engine=platform.monitoring_engine,
        execution_engine=platform.execution_engine,
        report_engine=platform.report_engine,
        backtest_engine=platform.backtest_engine,
    )["monitoring"]
    return {"ok": True, "monitoring": monitoring}


@app.post("/api/monitoring/stop")
async def api_monitoring_stop() -> dict[str, Any]:
    platform = _get_platform()
    platform.monitoring_engine.stop()
    monitoring = platform.dashboard_service.snapshot(
        analysis_engine=platform.analysis_engine,
        search_engine=platform.search_engine,
        monitoring_engine=platform.monitoring_engine,
        execution_engine=platform.execution_engine,
        report_engine=platform.report_engine,
        backtest_engine=platform.backtest_engine,
    )["monitoring"]
    return {"ok": True, "monitoring": monitoring}


@app.post("/api/monitoring/cycle")
async def api_monitoring_cycle() -> dict[str, Any]:
    platform = _get_platform()
    refreshed = platform.monitoring_engine.run_cycle()
    monitoring = platform.dashboard_service.snapshot(
        analysis_engine=platform.analysis_engine,
        search_engine=platform.search_engine,
        monitoring_engine=platform.monitoring_engine,
        execution_engine=platform.execution_engine,
        report_engine=platform.report_engine,
        backtest_engine=platform.backtest_engine,
    )["monitoring"]
    return {"ok": True, "watchlist": [item.symbol for item in refreshed], "monitoring": monitoring}


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
