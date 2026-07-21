from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from PIL import Image

from supreme_zone.core.settings import SettingsManager
from supreme_zone.modules.analysis_engine import AnalysisEngine
from supreme_zone.modules.data_engine.market import MarketBar
from supreme_zone.modules.data_engine.service import DataEngine
from supreme_zone.modules.strategy_manager.service import StrategyManager


def _write_strategy(path: Path) -> None:
    path.write_text(
        """
name: test_strategy
version: 1.0.0
analysis:
  timeframes: [D1, H4, H1, M15]
  minimum_candles: 20
  lookback_bars: 20
  zone_width_ratio: 0.25
  prefer_recent: true
  bias: neutral
""",
        encoding="utf-8",
    )


def _build_settings(tmp_path: Path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "default.yaml").write_text(
        f"""
app:
  name: Supreme Zone Platform
  log_level: INFO
market:
  symbols: [EURUSD]
  timeframes: [D1, H4, H1, M15]
  minimum_candles: 20
  history_window_candles: 20
storage:
  root: {tmp_path / 'storage'}
  charts: {tmp_path / 'storage/charts'}
  ohlc: {tmp_path / 'storage/ohlc'}
  reports: {tmp_path / 'storage/reports'}
  logs: {tmp_path / 'storage/logs'}
  cache: {tmp_path / 'storage/cache'}
  database: {tmp_path / 'storage/database'}
mt5:
  enabled: false
monitoring:
  enabled: false
""",
        encoding="utf-8",
    )
    return SettingsManager(config_dir / "default.yaml").load()


def _bars() -> list[MarketBar]:
    start = datetime(2026, 1, 1)
    bars: list[MarketBar] = []
    price = 1.0
    for index in range(40):
        direction = 1 if index >= 20 else -1
        open_ = price
        close = price + direction * 0.01
        high = max(open_, close) + 0.005
        low = min(open_, close) - 0.005
        bars.append(
            MarketBar(
                time=start + timedelta(minutes=index),
                open=open_,
                high=high,
                low=low,
                close=close,
                tick_volume=100 + index,
            )
        )
        price = close
    return bars


def test_analysis_engine_extracts_candidates(tmp_path) -> None:
    settings = _build_settings(tmp_path)
    data_engine = DataEngine(settings)
    strategy_manager = StrategyManager()

    strategy_file = tmp_path / "strategy.yaml"
    _write_strategy(strategy_file)
    strategy = strategy_manager.add_strategy_file(strategy_file)
    strategy_manager.activate_strategy(strategy.name)

    bars = _bars()
    for timeframe in ("D1", "H4", "H1", "M15"):
        data_engine.storage.save_ohlc("EURUSD", timeframe, bars)
        data_engine.database.upsert_bars("EURUSD", timeframe, bars)
        image_path = data_engine.storage.chart_path("EURUSD", timeframe)
        image_path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (1200, 800), color="white").save(image_path)

    engine = AnalysisEngine(settings=settings, data_engine=data_engine, strategy_manager=strategy_manager)
    report = engine.analyze_symbol("EURUSD")

    assert report.symbol == "EURUSD"
    assert report.strategy_name == "test_strategy"
    assert len(report.frame_analyses) == 4
    assert report.buy_zone is not None
    assert report.sell_zone is not None
    assert report.buy_zone.side.value == "BUY"
    assert report.sell_zone.side.value == "SELL"
    assert report.metadata["governance_required_score"] == 18
    assert "governance" in report.metadata
    assert report.metadata["governance"]["D1"]["buy"] is not None
    assert "score" in report.metadata["governance"]["D1"]["buy"]
    assert report.frame_analyses[0].image is not None
    assert report.frame_analyses[0].buy_candidate is not None
    assert report.frame_analyses[0].sell_candidate is not None


def test_strategy_profile_builder_reads_analysis_rules(tmp_path) -> None:
    settings = _build_settings(tmp_path)
    strategy_manager = StrategyManager()
    strategy_file = tmp_path / "strategy.yaml"
    _write_strategy(strategy_file)
    strategy = strategy_manager.add_strategy_file(strategy_file)

    from supreme_zone.modules.analysis_engine.strategy_profile import StrategyProfileBuilder

    profile = StrategyProfileBuilder().build(strategy)
    assert profile.name == "test_strategy"
    assert profile.timeframes == ("D1", "H4", "H1", "M15")
    assert profile.minimum_candles == 20
    assert profile.lookback_bars == 20
    assert profile.zone_width_ratio == 0.25
