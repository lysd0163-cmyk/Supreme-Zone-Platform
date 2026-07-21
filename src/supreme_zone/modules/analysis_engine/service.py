from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ...core.settings import Settings
from ..data_engine.database import MarketDatabase
from ..data_engine.service import DataEngine
from ..strategy_manager.models import StrategyDefinition
from ..strategy_manager.service import StrategyManager
from .analyzer import TimeframeAnalyzer
from .data_reader import AnalysisDataReader
from .image_reader import ChartImageInspector
from .models import AnalysisReport, AnalysisStrategyProfile, FrameAnalysis, ZoneCandidate
from .resolver import ZoneResolver
from .strategy_profile import StrategyProfileBuilder


@dataclass(slots=True)
class AnalysisEngineStatus:
    strategy_name: str | None = None
    analyzed_symbol: str | None = None
    analyzed_timeframes: tuple[str, ...] = ()
    last_report: AnalysisReport | None = None
    frame_count: int = 0


class AnalysisEngine:
    def __init__(
        self,
        settings: Settings,
        data_engine: DataEngine,
        strategy_manager: StrategyManager,
        data_reader: AnalysisDataReader | None = None,
        image_inspector: ChartImageInspector | None = None,
        analyzer: TimeframeAnalyzer | None = None,
        resolver: ZoneResolver | None = None,
        profile_builder: StrategyProfileBuilder | None = None,
    ) -> None:
        self.settings = settings
        self.data_engine = data_engine
        self.strategy_manager = strategy_manager
        self.data_reader = data_reader or AnalysisDataReader(storage=data_engine.storage, database=data_engine.database)
        self.image_inspector = image_inspector or ChartImageInspector()
        self.analyzer = analyzer or TimeframeAnalyzer()
        self.resolver = resolver or ZoneResolver()
        self.profile_builder = profile_builder or StrategyProfileBuilder()
        self.status = AnalysisEngineStatus()

    def _active_strategy(self, strategy_path: str | Path | None = None) -> StrategyDefinition:
        active = self.strategy_manager.registry.active()
        if active is not None:
            return active
        if strategy_path is not None:
            strategy = self.strategy_manager.add_strategy_file(strategy_path)
            self.strategy_manager.activate_strategy(strategy.name)
            return strategy
        configured = self.settings.strategy.active
        if configured:
            strategy = self.strategy_manager.add_strategy_file(configured)
            self.strategy_manager.activate_strategy(strategy.name)
            return strategy
        raise RuntimeError("No active strategy available")

    def _profile(self, strategy_path: str | Path | None = None) -> AnalysisStrategyProfile:
        definition = self._active_strategy(strategy_path)
        profile = self.profile_builder.build(definition)
        self.status.strategy_name = profile.name
        return profile

    def analyze_symbol(
        self,
        symbol: str,
        strategy_path: str | Path | None = None,
        timeframes: tuple[str, ...] | None = None,
        bars: int | None = None,
    ) -> AnalysisReport:
        profile = self._profile(strategy_path)
        selected_timeframes = tuple(tf.upper().strip() for tf in (timeframes or profile.timeframes or self.settings.timeframes))
        analyses: list[FrameAnalysis] = []

        for timeframe in selected_timeframes:
            frame_bars = self.data_reader.load_bars(symbol, timeframe, limit=bars or profile.minimum_candles)
            chart_path = self.data_reader.chart_path(symbol, timeframe)
            image = self.image_inspector.inspect(chart_path) if chart_path.exists() else None
            analysis = self.analyzer.analyze(symbol, timeframe, frame_bars, profile, image=image)
            analyses.append(analysis)

        buy_zone, sell_zone = self.resolver.resolve(tuple(analyses))
        self.status.analyzed_symbol = symbol.upper().strip()
        self.status.analyzed_timeframes = selected_timeframes
        self.status.last_report = AnalysisReport(
            symbol=symbol.upper().strip(),
            strategy_name=profile.name,
            frame_analyses=tuple(analyses),
            buy_zone=buy_zone,
            sell_zone=sell_zone,
            metadata={
                "selected_timeframes": selected_timeframes,
                "minimum_candles": profile.minimum_candles,
                "lookback_bars": profile.lookback_bars,
            },
        )
        self.status.frame_count = len(analyses)
        return self.status.last_report

    def analyze_all_symbols(
        self,
        strategy_path: str | Path | None = None,
        bars: int | None = None,
    ) -> tuple[AnalysisReport, ...]:
        reports: list[AnalysisReport] = []
        symbols = self.settings.symbols or self.data_engine.symbol_manager.symbols
        for symbol in symbols:
            reports.append(self.analyze_symbol(symbol, strategy_path=strategy_path, bars=bars))
        return tuple(reports)
