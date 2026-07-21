from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from ..data_engine.mt5_connector import MT5Connector
from ..entry_engine.models import EntrySignal, EntryStatus
from .models import ExecutionStatus, TradeRequest, TradeResult, TradeSide


@dataclass(slots=True)
class ExecutionEngine:
    connector: MT5Connector | None = None
    default_volume: float = 0.01
    magic: int = 10101
    _results: list[TradeResult] = field(default_factory=list, init=False)

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
        if self.connector is None:
            result = TradeResult(request=request, status=ExecutionStatus.FAILED, error="no-connector")
            self._results.append(result)
            return result

        try:
            response = self.connector.place_market_order(
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
        if self.connector is None:
            result = TradeResult(request=TradeRequest(symbol=symbol, side=side, volume=volume), status=ExecutionStatus.FAILED, error="no-connector")
            self._results.append(result)
            return result
        try:
            response = self.connector.close_position(ticket=ticket, symbol=symbol, volume=volume, side=side.value)
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
