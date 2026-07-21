from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Iterable

from ..analysis_engine.service import AnalysisEngine
from ..data_engine.market import MarketBar
from ..entry_engine.service import EntryEngine
from ..report_engine.service import ReportEngine
from ..report_engine.models import ReportBundle
from ..validation_engine.service import ValidationEngine
from .models import BacktestResult, BacktestState


@dataclass(slots=True)
class BacktestEngine:
    analysis_engine: AnalysisEngine
    validation_engine: ValidationEngine
    entry_engine: EntryEngine
    report_engine: ReportEngine | None = None
    state: BacktestState = field(default_factory=BacktestState)

    def run_symbol(self, symbol: str, bars_by_timeframe: dict[str, Iterable[MarketBar]], strategy_path: str | None = None) -> BacktestResult:
        try:
            report = self.analysis_engine.analyze_symbol(symbol, strategy_path=strategy_path)
            validation_map = self.validation_engine.validate_active_zones(report, bars_by_timeframe)
            trade_count = 0
            wins = 0
            losses = 0
            profit_points: list[float] = []
            loss_points: list[float] = []

            for timeframe, frame in ((item.timeframe, item) for item in report.frame_analyses):
                candidate = frame.buy_candidate or frame.sell_candidate
                if candidate is None:
                    continue
                bars = tuple(bars_by_timeframe.get(timeframe, ()))
                validation = validation_map.get("buy" if candidate.side.value == "BUY" else "sell")
                signal = self.entry_engine.evaluate(symbol, candidate, bars, validation=validation)
                if signal.status.value != "CONFIRMED":
                    continue
                trade_count += 1
                direction = 1.0 if candidate.side.value == "BUY" else -1.0
                score = candidate.score * direction
                if score >= 0:
                    wins += 1
                    profit_points.append(abs(score))
                else:
                    losses += 1
                    loss_points.append(abs(score))

            win_rate = (wins / trade_count * 100.0) if trade_count else 0.0
            profit_factor = (sum(profit_points) / max(sum(loss_points), 1e-9)) if loss_points or profit_points else 0.0
            result = BacktestResult(
                symbol=symbol.upper().strip(),
                strategy_name=report.strategy_name,
                trades=trade_count,
                wins=wins,
                losses=losses,
                win_rate=round(win_rate, 2),
                profit_factor=round(profit_factor, 4),
                start=self._first_time(bars_by_timeframe),
                end=self._last_time(bars_by_timeframe),
                metadata={"frames": len(report.frame_analyses), "strategy": report.strategy_name},
            )
            self.state.runs += 1
            self.state.last_symbol = result.symbol
            if self.report_engine is not None:
                self.report_engine.generate(ReportBundle(symbol=symbol, analysis=report, validation=validation_map, backtest={"result": asdict(result)}))
            return result
        except Exception as exc:
            self.state.last_error = str(exc)
            raise

    def run_all(self, bars_by_symbol: dict[str, dict[str, Iterable[MarketBar]]], strategy_path: str | None = None) -> tuple[BacktestResult, ...]:
        results: list[BacktestResult] = []
        for symbol, bars_by_timeframe in bars_by_symbol.items():
            results.append(self.run_symbol(symbol, bars_by_timeframe, strategy_path=strategy_path))
        return tuple(results)

    def _first_time(self, bars_by_timeframe: dict[str, Iterable[MarketBar]]) -> datetime | None:
        times = [bar.time for bars in bars_by_timeframe.values() for bar in bars]
        return min(times) if times else None

    def _last_time(self, bars_by_timeframe: dict[str, Iterable[MarketBar]]) -> datetime | None:
        times = [bar.time for bars in bars_by_timeframe.values() for bar in bars]
        return max(times) if times else None
