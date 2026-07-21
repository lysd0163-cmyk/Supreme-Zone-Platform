from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from PIL import Image

from supreme_zone.core.platform import SupremeZonePlatform
from supreme_zone.core.settings import AppSettings, ExecutionSettings, MarketSettings, MonitoringSettings, Settings, StrategySettings, StorageSettings, MT5Settings
from supreme_zone.modules.analysis_engine.models import AnalysisReport, FrameAnalysis, ZoneCandidate, ZoneSide
from supreme_zone.modules.analysis_engine.service import AnalysisEngine
from supreme_zone.modules.backtest_engine.service import BacktestEngine
from supreme_zone.modules.dashboard.service import DashboardService
from supreme_zone.modules.data_engine.market import MarketBar
from supreme_zone.modules.data_engine.service import DataEngine
from supreme_zone.modules.entry_engine.service import EntryEngine
from supreme_zone.modules.execution_engine.service import ExecutionEngine
from supreme_zone.modules.monitoring_engine.service import MonitoringEngine
from supreme_zone.modules.report_engine.service import ReportEngine
from supreme_zone.modules.search_engine.service import SearchEngine
from supreme_zone.modules.strategy_manager.service import StrategyManager
from supreme_zone.modules.validation_engine.service import ValidationEngine


@dataclass
class _FakeStrategyManager:
    registry: any = None

    def __post_init__(self) -> None:
        class _Registry:
            def active(self_inner):
                return None
        self.registry = _Registry()

    def add_strategy_file(self, path):
        from supreme_zone.modules.strategy_manager.models import StrategyDefinition
        return StrategyDefinition(name="test_strategy", version="1.0.0", source_path=Path(path), raw={"name": "test_strategy", "analysis": {"timeframes": ["D1", "H4", "H1", "M15"], "minimum_candles": 20, "lookback_bars": 20}}, active=True)

    def activate_strategy(self, name: str):
        return None


@dataclass
class _FakeDataReader:
    bars: tuple[MarketBar, ...]
    storage: any
    database: any

    def load_bars(self, symbol: str, timeframe: str, limit: int = 500):
        return self.bars

    def chart_path(self, symbol: str, timeframe: str) -> Path:
        return self.storage.chart_path(symbol, timeframe)


class _FakeDataEngine:
    def __init__(self, settings: Settings, bars: list[MarketBar]) -> None:
        self.settings = settings
        self.storage = settings.storage
        self.database = None
        self.status = type("Status", (), {"mt5_connected": False})()
        self.symbol_manager = type("SymbolManager", (), {"symbols": ("EURUSD",)})()
        self._bars = bars

    def connect_mt5(self) -> bool:
        return False

    def sync_all(self, bars: int | None = None):
        return []


class _FakeAnalysisEngine(AnalysisEngine):
    def __init__(self, settings: Settings, data_engine: DataEngine, strategy_manager: StrategyManager, bars: list[MarketBar]) -> None:
        super().__init__(settings=settings, data_engine=data_engine, strategy_manager=strategy_manager)
        self._bars = tuple(bars)
        self.data_reader = _FakeDataReader(self._bars, data_engine.storage, data_engine.database)

    def analyze_symbol(self, symbol: str, strategy_path: str | Path | None = None, bars: int | None = None):
        buy = ZoneCandidate(ZoneSide.BUY, "D1", symbol, 0.9, 1.0, 98.0, "test")
        sell = ZoneCandidate(ZoneSide.SELL, "D1", symbol, 1.1, 1.2, 96.0, "test")
        frame = FrameAnalysis(symbol=symbol, timeframe="D1", bars=self._bars, image=None, trend="flat", volatility=0.1, buy_candidate=buy, sell_candidate=sell)
        report = AnalysisReport(symbol=symbol, strategy_name="test_strategy", frame_analyses=(frame,), buy_zone=buy, sell_zone=sell, metadata={"minimum_candles": 20})
        self.status.strategy_name = "test_strategy"
        self.status.analyzed_symbol = symbol
        self.status.analyzed_timeframes = ("D1",)
        self.status.last_report = report
        self.status.frame_count = 1
        return report


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        app=AppSettings(),
        market=MarketSettings(symbols=("EURUSD",), timeframes=("D1", "H4", "H1", "M15"), minimum_candles=20, history_window_candles=20),
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
        mt5=MT5Settings(enabled=False),
        monitoring=MonitoringSettings(),
    )


def _bars() -> list[MarketBar]:
    start = datetime(2026, 1, 1)
    bars: list[MarketBar] = []
    price = 1.0
    for index in range(20):
        open_ = price
        close = price + (0.01 if index >= 10 else -0.01)
        high = max(open_, close) + 0.005
        low = min(open_, close) - 0.005
        bars.append(MarketBar(time=start + timedelta(minutes=index), open=open_, high=high, low=low, close=close, tick_volume=100 + index))
        price = close
    return bars


def test_platform_run_once_creates_dashboard_and_reports(tmp_path) -> None:
    settings = _settings(tmp_path)
    data_engine = _FakeDataEngine(settings, _bars())
    strategy_manager = _FakeStrategyManager()

    # Seed storage/database-like files used by the analysis reader.
    for timeframe in settings.timeframes:
        data_engine.storage.save_ohlc("EURUSD", timeframe, _bars())
        data_engine.storage.chart_path("EURUSD", timeframe).parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (1200, 800), color="white").save(data_engine.storage.chart_path("EURUSD", timeframe))

    analysis_engine = _FakeAnalysisEngine(settings, data_engine, strategy_manager, _bars())
    validation_engine = ValidationEngine()
    search_engine = SearchEngine(analysis_engine=analysis_engine, validation_engine=validation_engine)
    entry_engine = EntryEngine()
    execution_engine = ExecutionEngine(data_engine=None)
    monitoring_engine = MonitoringEngine(data_engine=data_engine, analysis_engine=analysis_engine, validation_engine=validation_engine, search_engine=search_engine, entry_engine=entry_engine, interval_seconds=1)
    report_engine = ReportEngine(output_dir=tmp_path / "reports")
    backtest_engine = BacktestEngine(analysis_engine=analysis_engine, validation_engine=validation_engine, entry_engine=entry_engine, report_engine=report_engine)
    dashboard_service = DashboardService(output_dir=tmp_path / "dashboard")

    platform = SupremeZonePlatform(
        data_engine=data_engine,
        analysis_engine=analysis_engine,
        validation_engine=validation_engine,
        search_engine=search_engine,
        entry_engine=entry_engine,
        execution_engine=execution_engine,
        monitoring_engine=monitoring_engine,
        report_engine=report_engine,
        backtest_engine=backtest_engine,
        dashboard_service=dashboard_service,
    )

    result = platform.run_once(strategy_path=tmp_path / "strategy.yaml")

    assert result.symbols == ("EURUSD",)
    assert result.dashboard_path is not None and result.dashboard_path.exists()
    assert result.dashboard_json is not None and result.dashboard_json.exists()
    assert result.report_artifacts
    assert platform.state.cycles == 1
    assert platform.state.last_error is None
