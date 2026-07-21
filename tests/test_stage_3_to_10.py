from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from supreme_zone.modules.analysis_engine.models import AnalysisReport, AnalysisStrategyProfile, FrameAnalysis, ZoneCandidate, ZoneSide
from supreme_zone.modules.backtest_engine.service import BacktestEngine
from supreme_zone.modules.dashboard.service import DashboardService
from supreme_zone.modules.data_engine.market import MarketBar
from supreme_zone.modules.entry_engine.service import EntryEngine
from supreme_zone.modules.execution_engine.models import ExecutionStatus, TradeSide
from supreme_zone.modules.execution_engine.service import ExecutionEngine
from supreme_zone.modules.monitoring_engine.models import MonitoredZone
from supreme_zone.modules.monitoring_engine.service import MonitoringEngine
from supreme_zone.modules.report_engine.models import ReportBundle
from supreme_zone.modules.report_engine.service import ReportEngine
from supreme_zone.modules.search_engine.models import SearchHit
from supreme_zone.modules.search_engine.service import SearchEngine
from supreme_zone.modules.validation_engine.service import ValidationEngine


@dataclass
class _FakeAnalysisEngine:
    settings: any
    data_engine: any
    strategy_manager: any

    def analyze_symbol(self, symbol: str, strategy_path: str | None = None, bars: int | None = None):
        bars_list = tuple(
            MarketBar(time=datetime(2026, 1, 1), open=1.0, high=1.1, low=0.9, close=1.05)
            for _ in range(20)
        )
        buy = ZoneCandidate(ZoneSide.BUY, "M15", symbol, 0.9, 1.0, 88.0, "test")
        sell = ZoneCandidate(ZoneSide.SELL, "M15", symbol, 1.1, 1.2, 86.0, "test")
        frame = FrameAnalysis(symbol=symbol, timeframe="M15", bars=bars_list, image=None, trend="flat", volatility=0.1, buy_candidate=buy, sell_candidate=sell)
        return AnalysisReport(symbol=symbol, strategy_name="test", frame_analyses=(frame,), buy_zone=buy, sell_zone=sell)


@dataclass
class _FakeDataEngine:
    settings: any

    def fetch_ohlc(self, symbol: str, timeframe: str, bars: int | None = None, use_cache: bool = True, force_refresh: bool = False):
        return [MarketBar(time=datetime(2026, 1, 1), open=1.0, high=1.1, low=0.9, close=1.05) for _ in range(20)]


@dataclass
class _FakeStrategyManager:
    registry: any = None

    def __post_init__(self):
        class _Registry:
            def active(self_inner):
                return None
        self.registry = _Registry()


class _FakeConnector:
    def place_market_order(self, **kwargs):
        return {"retcode": 10009, "request": kwargs}

    def close_position(self, **kwargs):
        return {"retcode": 10009, "request": kwargs}


class _FakeSettings:
    class storage:
        reports = Path("/tmp/reports")
        root = Path("/tmp/storage")
        charts = Path("/tmp/storage/charts")
        ohlc = Path("/tmp/storage/ohlc")
        logs = Path("/tmp/storage/logs")
        cache = Path("/tmp/storage/cache")
        database = Path("/tmp/storage/database")

    class market:
        live_poll_interval_seconds = 60
        history_window_candles = 20
        minimum_candles = 20

    class execution:
        lot_size = 0.01

    class monitoring:
        refresh_interval_seconds = 60

    symbols = ("EURUSD",)
    timeframes = ("M15",)
    strategy = type("S", (), {"active": None})()


def _candidate(side: ZoneSide) -> ZoneCandidate:
    if side is ZoneSide.BUY:
        return ZoneCandidate(side, "M15", "EURUSD", 0.9, 1.0, 90.0, "test")
    return ZoneCandidate(side, "M15", "EURUSD", 1.1, 1.2, 90.0, "test")


def test_validation_entry_execution_dashboard_and_report(tmp_path) -> None:
    validation = ValidationEngine()
    candidate = _candidate(ZoneSide.BUY)
    bars = [MarketBar(time=datetime(2026, 1, 1), open=1.0, high=1.05, low=0.95, close=1.02) for _ in range(10)]
    validation_result = validation.validate_candidate(candidate, bars)
    assert validation_result.candidate == candidate

    entry_engine = EntryEngine()
    signal = entry_engine.evaluate("EURUSD", candidate, bars + [MarketBar(time=datetime(2026, 1, 1), open=1.0, high=1.1, low=0.88, close=1.06)] * 4, validation=validation_result)
    assert signal.symbol == "EURUSD"

    execution_engine = ExecutionEngine(connector=_FakeConnector(), default_volume=0.01)
    trade_result = execution_engine.execute(signal)
    assert trade_result.status in {ExecutionStatus.SENT, ExecutionStatus.SKIPPED}

    report_engine = ReportEngine(output_dir=tmp_path / "reports")
    analysis = _FakeAnalysisEngine(settings=_FakeSettings(), data_engine=_FakeDataEngine(_FakeSettings()), strategy_manager=_FakeStrategyManager()).analyze_symbol("EURUSD")
    artifact = report_engine.generate(ReportBundle(symbol="EURUSD", analysis=analysis, validation={"buy": validation_result}, entry=signal, execution=trade_result, backtest={"trades": 1}))
    assert artifact.json_path.exists()
    assert artifact.markdown_path.exists()

    dashboard = DashboardService(output_dir=tmp_path / "dashboard")
    snapshot = dashboard.snapshot(
        analysis_engine=_FakeAnalysisEngine(settings=_FakeSettings(), data_engine=_FakeDataEngine(_FakeSettings()), strategy_manager=_FakeStrategyManager()),
    )
    html_path = dashboard.render(snapshot)
    assert html_path.exists()


def test_search_engine_accepts_valid_hits(tmp_path) -> None:
    analysis_engine = _FakeAnalysisEngine(settings=_FakeSettings(), data_engine=_FakeDataEngine(_FakeSettings()), strategy_manager=_FakeStrategyManager())
    validation_engine = ValidationEngine()
    search_engine = SearchEngine(analysis_engine=analysis_engine, validation_engine=validation_engine)
    hit = search_engine.search_symbol("EURUSD")
    assert hit is not None
    assert isinstance(hit, SearchHit)


def test_monitoring_engine_cycle_and_backtest(tmp_path) -> None:
    analysis_engine = _FakeAnalysisEngine(settings=_FakeSettings(), data_engine=_FakeDataEngine(_FakeSettings()), strategy_manager=_FakeStrategyManager())
    validation_engine = ValidationEngine()
    search_engine = SearchEngine(analysis_engine=analysis_engine, validation_engine=validation_engine)
    entry_engine = EntryEngine()
    data_engine = _FakeDataEngine(_FakeSettings())
    monitoring = MonitoringEngine(
        data_engine=data_engine,
        analysis_engine=analysis_engine,
        validation_engine=validation_engine,
        search_engine=search_engine,
        entry_engine=entry_engine,
        interval_seconds=1,
    )
    monitoring.watch(MonitoredZone(symbol="EURUSD", candidate=_candidate(ZoneSide.BUY)))
    cycle = monitoring.run_cycle()
    assert cycle

    report_engine = ReportEngine(output_dir=tmp_path / "reports")
    backtest = BacktestEngine(analysis_engine=analysis_engine, validation_engine=validation_engine, entry_engine=entry_engine, report_engine=report_engine)
    result = backtest.run_symbol("EURUSD", {"M15": [MarketBar(time=datetime(2026, 1, 1), open=1.0, high=1.1, low=0.9, close=1.05) for _ in range(20)]})
    assert result.symbol == "EURUSD"
