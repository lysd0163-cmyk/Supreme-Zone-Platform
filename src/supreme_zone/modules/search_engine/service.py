from __future__ import annotations

from dataclasses import dataclass, field
from threading import Event, Thread
from time import sleep
from typing import Iterable

from ..analysis_engine.service import AnalysisEngine
from ..data_engine.market import MarketBar
from ..validation_engine.service import ValidationEngine
from .models import SearchHit, SearchState


@dataclass(slots=True)
class SearchEngine:
    analysis_engine: AnalysisEngine
    validation_engine: ValidationEngine
    state: SearchState = field(default_factory=SearchState)
    _stop_event: Event = field(default_factory=Event, init=False)
    _thread: Thread | None = field(default=None, init=False)
    _hits: list[SearchHit] = field(default_factory=list, init=False)

    def search_symbol(self, symbol: str, strategy_path: str | None = None, bars: int | None = None) -> SearchHit | None:
        report = self.analysis_engine.analyze_symbol(symbol, strategy_path=strategy_path, bars=bars)
        bars_by_timeframe = {frame.timeframe: frame.bars for frame in report.frame_analyses}
        validation_map = self.validation_engine.validate_active_zones(report, bars_by_timeframe)

        candidates = [report.buy_zone, report.sell_zone]
        best_candidate = None
        best_validation = None
        for candidate in candidates:
            if candidate is None:
                continue
            validation = validation_map.get("buy" if candidate.side.value == "BUY" else "sell")
            if validation is not None and validation.is_valid:
                if best_candidate is None or candidate.score > best_candidate.score:
                    best_candidate = candidate
                    best_validation = validation

        self.state.total_scanned += 1
        self.state.last_symbol = symbol.upper().strip()
        if best_candidate is None:
            return None

        hit = SearchHit(symbol=symbol.upper().strip(), report=report, validation=best_validation, candidate=best_candidate)
        self._hits.append(hit)
        self.state.total_hits += 1
        return hit

    def search_all(self, strategy_path: str | None = None, bars: int | None = None) -> tuple[SearchHit, ...]:
        hits: list[SearchHit] = []
        for symbol in self.analysis_engine.settings.symbols or self.analysis_engine.data_engine.symbol_manager.symbols:
            hit = self.search_symbol(symbol, strategy_path=strategy_path, bars=bars)
            if hit is not None:
                hits.append(hit)
        return tuple(hits)

    def run_continuous(self, strategy_path: str | None = None, bars: int | None = None, interval_seconds: int = 60) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = Thread(target=self._loop, args=(strategy_path, bars, interval_seconds), daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)

    def _loop(self, strategy_path: str | None, bars: int | None, interval_seconds: int) -> None:
        while not self._stop_event.is_set():
            try:
                self.search_all(strategy_path=strategy_path, bars=bars)
                self.state.last_error = None
            except Exception as exc:  # pragma: no cover - runtime safety
                self.state.last_error = str(exc)
            sleep(max(interval_seconds, 1))

    @property
    def hits(self) -> tuple[SearchHit, ...]:
        return tuple(self._hits)
