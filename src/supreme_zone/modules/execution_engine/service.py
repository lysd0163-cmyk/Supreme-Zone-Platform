from __future__ import annotations

from dataclasses import dataclass, field

from ..data_engine.mt5_connector import MT5Connector
from ..data_engine.service import DataEngine
from ..entry_engine.models import EntrySignal, EntryStatus
from .models import ExecutionStatus, TradeRequest, TradeResult, TradeSide


@dataclass(slots=True)
class ExecutionEngine:
    connector: MT5Connector | None = None
    data_engine: DataEngine | None = None
    default_volume: float = 0.01
    magic: int = 10101
    _results: list[TradeResult] = field(default_factory=list, init=False)

    def _active_connector(self) -> MT5Connector | None:
        if self.connector is not None:
            return self.connector
        if self.data_engine is not None:
            if self.data_engine._connector is not None:  # noqa: SLF001 - runtime bridge
                return self.data_engine._connector
            try:
                return self.data_engine.build_mt5_connector()
            except Exception:
                return None
        return None

    def open_positions(self, symbol: str | None = None) -> list[dict[str, object]]:
        connector = self._active_connector()
        if connector is None:
            return []
        try:
            return connector.open_positions(symbol=symbol)
        except Exception:
            return []

    def execute(self, signal: EntrySignal | None) -> TradeResult:
        if signal is None:
            result = TradeResult(
                request=TradeRequest(symbol="", side=TradeSide.BUY, volume=self.default_volume),
                status=ExecutionStatus.SKIPPED,
                error="no-signal",
            )
            self._results.append(result)
            return result

        if signal.status is not EntryStatus.CONFIRMED or signal.entry_price is None:
            result = TradeResult(
                request=self._request_from_signal(signal),
                status=ExecutionStatus.SKIPPED,
                error=f"signal-not-ready:{signal.status.value}",
            )
            self._results.append(result)
            return result

        request = self._request_from_signal(signal)
        connector = self._active_connector()
        if connector is None:
            result = TradeResult(request=request, status=ExecutionStatus.FAILED, error="no-connector")
            self._results.append(result)
            return result

        try:
            response = connector.place_market_order(
                symbol=request.symbol,
                volume=request.volume,
                side=request.side.value,
                sl=request.stop_loss,
                tp=request.take_profit,
                comment=request.comment,
                magic=request.magic,
            )
            result = TradeResult(request=request, status=ExecutionStatus.SENT, broker_response=response)
        except Exception as exc:
            result = TradeResult(request=request, status=ExecutionStatus.FAILED, error=str(exc))
        self._results.append(result)
        return result

    def close(self, ticket: int, symbol: str, volume: float, side: TradeSide) -> TradeResult:
        connector = self._active_connector()
        if connector is None:
            result = TradeResult(request=TradeRequest(symbol=symbol, side=side, volume=volume), status=ExecutionStatus.FAILED, error="no-connector")
            self._results.append(result)
            return result
        try:
            response = connector.close_position(ticket=ticket, symbol=symbol, volume=volume, side=side.value)
            request = TradeRequest(symbol=symbol, side=side, volume=volume)
            result = TradeResult(request=request, status=ExecutionStatus.SENT, broker_response=response)
        except Exception as exc:
            request = TradeRequest(symbol=symbol, side=side, volume=volume)
            result = TradeResult(request=request, status=ExecutionStatus.FAILED, error=str(exc))
        self._results.append(result)
        return result

    def _request_from_signal(self, signal: EntrySignal) -> TradeRequest:
        side = TradeSide.BUY if signal.side.value == "BUY" else TradeSide.SELL
        return TradeRequest(
            symbol=signal.symbol,
            side=side,
            volume=self.default_volume,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
            comment=f"{signal.symbol}:{signal.timeframe}:{signal.status.value}",
            magic=self.magic,
            source_signal=signal,
            metadata={"candidate_score": signal.candidate.score},
        )

    @property
    def results(self) -> tuple[TradeResult, ...]:
        return tuple(self._results)
