from __future__ import annotations

from dataclasses import dataclass, field
from threading import Event, Thread
from time import sleep
from typing import Iterable

from ..analysis_engine.service import AnalysisEngine
from ..data_engine.service import DataEngine
from ..entry_engine.service import EntryEngine
from ..search_engine.service import SearchEngine
from ..validation_engine.service import ValidationEngine
from .models import MonitoredZone, MonitoringState


@dataclass(slots=True)
class MonitoringEngine:
    data_engine: DataEngine
    analysis_engine: AnalysisEngine
    validation_engine: ValidationEngine
    search_engine: SearchEngine
    entry_engine: EntryEngine
    interval_seconds: int = 60
    state: MonitoringState = field(default_factory=MonitoringState)
    _watchlist: list[MonitoredZone] = field(default_factory=list, init=False)
    _stop_event: Event = field(default_factory=Event, init=False)
    _thread: Thread | None = field(default=None, init=False)

    def watch(self, monitored_zone: MonitoredZone) -> None:
        self._watchlist.append(monitored_zone)

    def unwatch(self, symbol: str, timeframe: str | None = None) -> None:
        normalized_symbol = symbol.upper().strip()
        normalized_timeframe = timeframe.upper().strip() if timeframe else None
        self._watchlist = [
            item for item in self._watchlist
            if not (
                item.symbol.upper().strip() == normalized_symbol
                and (normalized_timeframe is None or item.candidate.timeframe.upper().strip() == normalized_timeframe)
            )
        ]

    def run_cycle(self) -> list[MonitoredZone]:
        refreshed: list[MonitoredZone] = []
        for item in list(self._watchlist):
            bars = self.data_engine.fetch_ohlc(item.symbol, item.candidate.timeframe, bars=self.data_engine.settings.market.history_window_candles)
            report = self.analysis_engine.analyze_symbol(item.symbol)
            bars_by_timeframe = {frame.timeframe: frame.bars for frame in report.frame_analyses}
            validation = self.validation_engine.validate_candidate(item.candidate, bars_by_timeframe.get(item.candidate.timeframe, ()))
            if not validation.is_valid:
                self.state.invalidations += 1
                hit = self.search_engine.search_symbol(item.symbol)
                if hit is not None:
                    item = MonitoredZone(symbol=item.symbol, candidate=hit.candidate or item.candidate, validation=hit.validation, report=hit.report, metadata={"reanalysed": True})
                self.state.reanalyses += 1
            else:
                entry = self.entry_engine.evaluate(item.symbol, item.candidate, bars_by_timeframe.get(item.candidate.timeframe, ()), validation=validation)
                item = MonitoredZone(symbol=item.symbol, candidate=item.candidate, validation=validation, entry=entry, report=report)
            refreshed.append(item)
        self._watchlist = refreshed
        self.state.cycles += 1
        return refreshed

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self.state.running = True
        self._thread = Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        self.state.running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.run_cycle()
                self.state.last_error = None
            except Exception as exc:  # pragma: no cover - runtime safety
                self.state.last_error = str(exc)
            sleep(max(self.interval_seconds, 1))

    @property
    def watchlist(self) -> tuple[MonitoredZone, ...]:
        return tuple(self._watchlist)
