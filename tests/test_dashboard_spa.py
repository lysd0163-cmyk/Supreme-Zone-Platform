from __future__ import annotations

from pathlib import Path

from supreme_zone.modules.dashboard.service import DashboardService


def test_dashboard_renders_spa_html(tmp_path) -> None:
    service = DashboardService(output_dir=tmp_path)
    snapshot = {
        "generated_at": "2026-01-01T00:00:00Z",
        "analysis": {
            "strategy_name": "demo",
            "symbol": "EURUSD",
            "timeframes": ["D1", "H4"],
            "frame_count": 2,
            "buy_zone": {"side": "BUY", "timeframe": "D1", "lower": 1.0, "upper": 1.1, "score": 95.0},
            "sell_zone": {"side": "SELL", "timeframe": "H4", "lower": 1.2, "upper": 1.3, "score": 90.0},
            "frames": [],
        },
        "search": {"total_scanned": 1, "total_hits": 1, "hits": []},
        "monitoring": {"running": False, "cycles": 0, "watchlist": []},
        "execution": {"results": 0, "last_result": None},
        "reports": {"artifacts": 0, "files": []},
        "backtest": {"runs": 0, "last_error": None},
    }

    json_path = service.export_json(snapshot)
    html_path = service.render(snapshot)
    html = html_path.read_text(encoding="utf-8")

    assert json_path.exists()
    assert html_path.exists()
    assert "dashboard-data" in html
    assert "sectionSelect" in html
    assert "Copy JSON" in html
    assert "function renderOverview" in html
    assert "function renderAnalysis" in html
    assert "EURUSD" in html
