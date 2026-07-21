from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from ..analysis_engine.models import ZoneCandidate, ZoneSide
from ..data_engine.market import MarketBar
from ..validation_engine.models import ZoneValidationResult
from .models import EntrySignal, EntryStatus


@dataclass(slots=True)
class EntryEngine:
    risk_reward_ratio: float = 2.0
    buffer_ratio: float = 0.1
    _signals: list[EntrySignal] = field(default_factory=list, init=False)

    def evaluate(self, symbol: str, candidate: ZoneCandidate, bars_m15: Iterable[MarketBar], validation: ZoneValidationResult | None = None) -> EntrySignal:
        bars = tuple(bars_m15)
        if len(bars) < 4:
            signal = self._waiting(symbol, candidate, validation, "insufficient-bars")
            self._signals.append(signal)
            return signal

        break_bar = bars[-3]
        retest_bar = bars[-2]
        confirm_bar = bars[-1]

        break_confirmed = self._break_confirmed(candidate, break_bar)
        retest_confirmed = self._retest_confirmed(candidate, retest_bar)
        confirmation = self._confirmation(candidate, confirm_bar)

        if not all((break_confirmed, retest_confirmed, confirmation)):
            status = EntryStatus.WAITING
            evidence = (
                f"break={break_confirmed}",
                f"retest={retest_confirmed}",
                f"confirm={confirmation}",
            )
            signal = self._signal(symbol, candidate, validation, status, None, None, None, evidence)
            self._signals.append(signal)
            return signal

        entry_price = confirm_bar.close
        stop_loss, take_profit = self._sl_tp(candidate, entry_price)
        signal = self._signal(
            symbol,
            candidate,
            validation,
            EntryStatus.CONFIRMED,
            entry_price,
            stop_loss,
            take_profit,
            (
                f"break_bar_close={break_bar.close}",
                f"retest_bar_close={retest_bar.close}",
                f"confirm_bar_close={confirm_bar.close}",
            ),
        )
        self._signals.append(signal)
        return signal

    def _waiting(self, symbol: str, candidate: ZoneCandidate, validation: ZoneValidationResult | None, reason: str) -> EntrySignal:
        return self._signal(symbol, candidate, validation, EntryStatus.WAITING, None, None, None, (reason,))

    def _signal(
        self,
        symbol: str,
        candidate: ZoneCandidate,
        validation: ZoneValidationResult | None,
        status: EntryStatus,
        entry_price: float | None,
        stop_loss: float | None,
        take_profit: float | None,
        evidence: tuple[str, ...],
    ) -> EntrySignal:
        return EntrySignal(
            symbol=symbol.upper().strip(),
            timeframe=candidate.timeframe,
            side=candidate.side,
            status=status,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            candidate=candidate,
            validation=validation,
            evidence=evidence,
            metadata={"risk_reward_ratio": self.risk_reward_ratio},
        )

    def _break_confirmed(self, candidate: ZoneCandidate, bar: MarketBar) -> bool:
        if candidate.side is ZoneSide.BUY:
            return bar.close > candidate.upper
        return bar.close < candidate.lower

    def _retest_confirmed(self, candidate: ZoneCandidate, bar: MarketBar) -> bool:
        return bar.low <= candidate.upper and bar.high >= candidate.lower

    def _confirmation(self, candidate: ZoneCandidate, bar: MarketBar) -> bool:
        if candidate.side is ZoneSide.BUY:
            return bar.close > bar.open and bar.close >= candidate.upper
        return bar.close < bar.open and bar.close <= candidate.lower

    def _sl_tp(self, candidate: ZoneCandidate, entry_price: float) -> tuple[float, float]:
        span = max(candidate.width, abs(entry_price) * 0.0005)
        if candidate.side is ZoneSide.BUY:
            stop_loss = candidate.lower - span * self.buffer_ratio
            take_profit = entry_price + span * self.risk_reward_ratio
        else:
            stop_loss = candidate.upper + span * self.buffer_ratio
            take_profit = entry_price - span * self.risk_reward_ratio
        return float(stop_loss), float(take_profit)

    @property
    def signals(self) -> tuple[EntrySignal, ...]:
        return tuple(self._signals)
