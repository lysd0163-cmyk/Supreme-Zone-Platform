from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from supreme_zone.core.settings import (
    AppSettings,
    ExecutionSettings,
    MarketSettings,
    MonitoringSettings,
    Settings,
    StrategySettings,
    StorageSettings,
    MT5Settings,
)
from supreme_zone.modules.data_engine.market import MarketBar
from supreme_zone.modules.data_engine.service import DataEngine
from supreme_zone.modules.data_engine.chart_renderer import ChartRenderer


@dataclass
class _FakeConnector:
    connected: bool = True

    def is_connected(self) -> bool:
        return self.connected

    def fetch_rates(self, request):
        start = datetime(2026, 1, 1)
        bars = []
        price = 1.0
        for index in range(request.bars):
            bars.append(
                {
                    "time": start + timedelta(minutes=index),
                    "open": price,
                    "high": price + 0.02,
                    "low": price - 0.02,
                    "close": price + 0.01,
                    "tick_volume": 100 + index,
                }
            )
            price += 0.01
        return bars

    def shutdown(self) -> None:
        self.connected = False


class _FakeRenderer:
    def render(self, bars, output_path: Path, title: str | None = None) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(f"{title or 'chart'}:{len(list(bars))}", encoding="utf-8")
        return output_path


def _build_settings(tmp_path: Path) -> Settings:
    return Settings(
        app=AppSettings(),
        market=MarketSettings(symbols=("EURUSD",), timeframes=("M15",), minimum_candles=500, history_window_candles=500),
        strategy=StrategySettings(),
        storage=StorageSettings(
            root=tmp_path / "storage",
            charts=tmp_path / "storage/charts",
            ohlc=tmp_path / "storage/ohlc",
            reports=tmp_path / "storage/reports",
            logs=tmp_path / "storage/logs",
            cache=tmp_path / "storage/cache",
            database=tmp_path / "storage/database",
        ),
        execution=ExecutionSettings(),
        mt5=MT5Settings(enabled=True, server="Demo", login=12345, password="secret"),
        monitoring=MonitoringSettings(),
    )


def test_data_engine_fetches_500_bars_and_persists(tmp_path) -> None:
    engine = DataEngine(_build_settings(tmp_path), renderer=_FakeRenderer())
    engine._connector = _FakeConnector()  # noqa: SLF001 - test seam

    bars = engine.fetch_ohlc("EURUSD", "M15")

    assert len(bars) == 500
    assert all(isinstance(bar, MarketBar) for bar in bars)
    assert engine.status.last_ohlc_path == tmp_path / "storage/ohlc/EURUSD_M15.json"
    assert engine.status.last_ohlc_path.exists()

    sync_result = engine.sync_market("EURUSD", "M15")
    assert sync_result["bars"] == 500
    assert sync_result["chart_path"] == tmp_path / "storage/charts/EURUSD_M15.png"
    assert sync_result["chart_path"].exists()


def test_chart_renderer_writes_png(tmp_path) -> None:
    bars = [
        MarketBar(
            time=datetime(2026, 1, 1, 0, 0) + timedelta(minutes=index),
            open=1.0 + index * 0.01,
            high=1.02 + index * 0.01,
            low=0.98 + index * 0.01,
            close=1.01 + index * 0.01,
        )
        for index in range(20)
    ]
    renderer = ChartRenderer()
    output = renderer.render(bars, tmp_path / "chart.png", title="EURUSD M15")

    assert output.exists()
    assert output.suffix == ".png"
