from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from ..modules.analysis_engine.models import AnalysisReport
from ..modules.analysis_engine.service import AnalysisEngine
from ..modules.backtest_engine.service import BacktestEngine
from ..modules.dashboard.service import DashboardService
from ..modules.data_engine.service import DataEngine
from ..modules.entry_engine.models import EntrySignal
from ..modules.entry_engine.service import EntryEngine
from ..modules.execution_engine.models import TradeResult
from ..modules.execution_engine.service import ExecutionEngine
from ..modules.monitoring_engine.models import MonitoredZone
from ..modules.monitoring_engine.service import MonitoringEngine
from ..modules.report_engine.models import ReportBundle, ReportArtifact
from ..modules.report_engine.service import ReportEngine
from ..modules.search_engine.models import SearchHit
from ..modules.search_engine.service import SearchEngine
from ..modules.validation_engine.models import ZoneValidationResult
from ..modules.validation_engine.service import ValidationEngine


@dataclass(slots=True)
class PlatformRunResult:
    symbols: tuple[str, ...]
    analysis_reports: tuple[AnalysisReport, ...]
    search_hits: tuple[SearchHit, ...]
    validations: dict[str, ZoneValidationResult]
    entries: tuple[EntrySignal, ...]
    executions: tuple[TradeResult, ...]
    report_artifacts: tuple[ReportArtifact, ...]
    dashboard_path: Path | None
    dashboard_json: Path | None
    backtest_results: tuple[Any, ...] = ()


@dataclass(slots=True)
class PlatformState:
    cycles: int = 0
    last_error: str | None = None
    last_dashboard: Path | None = None


@dataclass(slots=True)
class SupremeZonePlatform:
    data_engine: DataEngine
    analysis_engine: AnalysisEngine
    validation_engine: ValidationEngine
    search_engine: SearchEngine
    entry_engine: EntryEngine
    execution_engine: ExecutionEngine
    monitoring_engine: MonitoringEngine
    report_engine: ReportEngine
    backtest_engine: BacktestEngine
    dashboard_service: DashboardService
    state: PlatformState = field(default_factory=PlatformState)

    def run_once(
        self,
        strategy_path: str | Path | None = None,
        bars: int | None = None,
        symbols: Iterable[str] | None = None,
    ) -> PlatformRunResult:
        try:
            profile = self.analysis_engine._profile(strategy_path)
            selected_symbols = tuple(symbols or self.data_engine.settings.symbols or self.data_engine.symbol_manager.symbols)
            selected_timeframes = tuple(tf.upper().strip() for tf in (profile.timeframes or self.data_engine.timeframe_manager.supported))
            self._ensure_market_data_ready(selected_symbols, selected_timeframes, bars=bars, minimum_candles=profile.minimum_candles)

            analysis_reports: list[AnalysisReport] = []
            search_hits: list[SearchHit] = []
            validations: dict[str, ZoneValidationResult] = {}
            entries: list[EntrySignal] = []
            executions: list[TradeResult] = []
            report_artifacts: list[ReportArtifact] = []
            backtest_results: list[Any] = []

            for symbol in selected_symbols:
                report = self.analysis_engine.analyze_symbol(symbol, strategy_path=strategy_path, bars=bars)
                analysis_reports.append(report)

                frame_limit = bars or report.metadata.get("minimum_candles", 500)
                bars_by_timeframe = {
                    frame.timeframe: self.analysis_engine.data_reader.load_bars(symbol, frame.timeframe, limit=frame_limit)
                    for frame in report.frame_analyses
                }
                validation_map = self.validation_engine.validate_active_zones(report, bars_by_timeframe)
                for key, value in validation_map.items():
                    validations[f"{symbol}:{key}"] = value

                hit = self.search_engine.search_symbol(symbol, strategy_path=strategy_path, bars=bars)
                candidate = hit.candidate if hit is not None else report.buy_zone or report.sell_zone
                validation = hit.validation if hit is not None else None
                if hit is not None:
                    search_hits.append(hit)

                if candidate is not None:
                    m15_bars = bars_by_timeframe.get("M15", ())
                    entry = self.entry_engine.evaluate(symbol, candidate, m15_bars, validation=validation)
                    entries.append(entry)
                    execution = self.execution_engine.execute(entry)
                    executions.append(execution)
                    report_bundle = ReportBundle(symbol=symbol, analysis=report, validation=validation_map, entry=entry, execution=execution, backtest={})
                    self.monitoring_engine.watch(
                        MonitoredZone(symbol=symbol, candidate=candidate, validation=validation, entry=entry, report=report)
                    )
                    backtest_results.append(self.backtest_engine.run_symbol(symbol, bars_by_timeframe, strategy_path=strategy_path))
                else:
                    report_bundle = ReportBundle(symbol=symbol, analysis=report, validation=validation_map, backtest={})

                report_artifacts.append(self.report_engine.generate(report_bundle))

            snapshot = self.dashboard_service.snapshot(
                analysis_engine=self.analysis_engine,
                search_engine=self.search_engine,
                monitoring_engine=self.monitoring_engine,
                execution_engine=self.execution_engine,
                report_engine=self.report_engine,
                backtest_engine=self.backtest_engine,
            )
            dashboard_json = self.dashboard_service.export_json(snapshot)
            dashboard_path = self.dashboard_service.render(snapshot)
            self.state.cycles += 1
            self.state.last_dashboard = dashboard_path
            self.state.last_error = None
            return PlatformRunResult(
                symbols=selected_symbols,
                analysis_reports=tuple(analysis_reports),
                search_hits=tuple(search_hits),
                validations=validations,
                entries=tuple(entries),
                executions=tuple(executions),
                report_artifacts=tuple(report_artifacts),
                dashboard_path=dashboard_path,
                dashboard_json=dashboard_json,
                backtest_results=tuple(backtest_results),
            )
        except Exception as exc:
            self.state.last_error = str(exc)
            raise

    def _ensure_market_data_ready(
        self,
        symbols: Iterable[str],
        timeframes: Iterable[str],
        bars: int | None = None,
        minimum_candles: int = 500,
    ) -> None:
        symbols = tuple(str(symbol).upper().strip() for symbol in symbols if str(symbol).strip())
        timeframes = tuple(str(timeframe).upper().strip() for timeframe in timeframes if str(timeframe).strip())
        if not symbols:
            raise RuntimeError("No symbols configured for analysis")
        if not timeframes:
            raise RuntimeError("No timeframes configured for analysis")

        if self.data_engine.data_source == "mt5" and self.data_engine.settings.mt5.enabled and not self.data_engine.status.mt5_connected:
            self.data_engine.connect_mt5()

        sync_results = self.data_engine.sync_all(bars=bars)
        errors: list[str] = []
        for result in sync_results:
            if str(result.get("status", "")).lower() == "error":
                errors.append(f"{result.get('symbol')} {result.get('timeframe')}: {result.get('error')}")
                continue
            if int(result.get("bars") or 0) < minimum_candles:
                errors.append(f"{result.get('symbol')} {result.get('timeframe')}: {int(result.get('bars') or 0)} < {minimum_candles}")
        if errors:
            raise RuntimeError("Data sync incomplete: " + "; ".join(errors[:4]))

        reader = self.analysis_engine.data_reader
        for symbol in symbols:
            for timeframe in timeframes:
                bars_loaded = reader.load_bars(symbol, timeframe, limit=minimum_candles)
                if len(bars_loaded) < minimum_candles:
                    raise RuntimeError(f"Not enough OHLC bars for {symbol} {timeframe}: {len(bars_loaded)} < {minimum_candles}")

    def run_forever(self, interval_seconds: int = 60, **kwargs: Any) -> None:
        from time import sleep

        while True:
            self.run_once(**kwargs)
            sleep(max(interval_seconds, 1))