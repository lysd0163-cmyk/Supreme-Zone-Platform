from __future__ import annotations

from dataclasses import dataclass, field
from statistics import mean
from typing import Iterable

from ..data_engine.market import MarketBar
from .models import AnalysisStrategyProfile, FrameAnalysis, ZoneCandidate, ZoneSide


LAYER_NAMES: tuple[str, ...] = (
    "liquidity_intent",
    "external_liquidity",
    "origin",
    "displacement",
    "order_block",
    "fair_value_gap",
    "structure",
    "premium_discount",
    "internal_liquidity",
    "liquidity_sweep",
    "repricing",
    "order_flow",
    "momentum",
    "execution_path",
    "stop_loss_safety",
    "risk_reward",
    "higher_timeframe_confluence",
    "absolute_market_maker_confluence",
)


@dataclass(slots=True, frozen=True)
class LayerCheck:
    name: str
    passed: bool
    evidence: tuple[str, ...] = ()


@dataclass(slots=True, frozen=True)
class GovernanceAudit:
    side: ZoneSide
    timeframe: str
    symbol: str
    checks: tuple[LayerCheck, ...]
    score: int
    required: int = 18

    @property
    def passed(self) -> bool:
        return self.score >= self.required

    @property
    def failed_layers(self) -> tuple[str, ...]:
        return tuple(check.name for check in self.checks if not check.passed)

    @property
    def passed_layers(self) -> tuple[str, ...]:
        return tuple(check.name for check in self.checks if check.passed)


@dataclass(slots=True)
class GovernanceEngine:
    required_score: int = 18

    def evaluate(
        self,
        candidate: ZoneCandidate,
        frame: FrameAnalysis,
        profile: AnalysisStrategyProfile,
        higher_timeframes: Iterable[FrameAnalysis] = (),
    ) -> GovernanceAudit:
        bars = frame.bars
        higher = tuple(higher_timeframes)
        checks = [
            self._liquidity_intent(candidate, frame, profile),
            self._external_liquidity(candidate, frame),
            self._origin(candidate, frame),
            self._displacement(candidate, frame),
            self._order_block(candidate, frame),
            self._fair_value_gap(candidate, frame),
            self._structure(candidate, frame),
            self._premium_discount(candidate, frame, higher),
            self._internal_liquidity(candidate, frame),
            self._liquidity_sweep(candidate, frame),
            self._repricing(candidate, frame),
            self._order_flow(candidate, frame, higher),
            self._momentum(candidate, frame),
            self._execution_path(candidate, frame, higher),
            self._stop_loss_safety(candidate, frame),
            self._risk_reward(candidate, frame),
            self._higher_timeframe_confluence(candidate, frame, higher),
            self._absolute_market_maker_confluence(candidate, frame, higher),
        ]
        score = sum(1 for check in checks if check.passed)
        return GovernanceAudit(side=candidate.side, timeframe=candidate.timeframe, symbol=candidate.symbol, checks=tuple(checks), score=score, required=self.required_score)

    def _liquidity_intent(self, candidate: ZoneCandidate, frame: FrameAnalysis, profile: AnalysisStrategyProfile) -> LayerCheck:
        trend = frame.trend
        passed = (candidate.side is ZoneSide.BUY and trend in {"up", "flat"}) or (candidate.side is ZoneSide.SELL and trend in {"down", "flat"})
        return LayerCheck("liquidity_intent", passed, (f"trend={trend}", f"bias={profile.bias}"))

    def _external_liquidity(self, candidate: ZoneCandidate, frame: FrameAnalysis) -> LayerCheck:
        highs = frame.swing_highs
        lows = frame.swing_lows
        if candidate.side is ZoneSide.BUY:
            passed = bool(lows) and candidate.lower <= min(lows[-3:]) + frame.volatility * 2
        else:
            passed = bool(highs) and candidate.upper >= max(highs[-3:]) - frame.volatility * 2
        return LayerCheck("external_liquidity", passed, (f"highs={len(highs)}", f"lows={len(lows)}"))

    def _origin(self, candidate: ZoneCandidate, frame: FrameAnalysis) -> LayerCheck:
        pivot_count = len(frame.swing_highs) + len(frame.swing_lows)
        passed = pivot_count > 0 and candidate.score > 0
        return LayerCheck("origin", passed, (f"pivots={pivot_count}", f"score={candidate.score}"))

    def _displacement(self, candidate: ZoneCandidate, frame: FrameAnalysis) -> LayerCheck:
        recent = frame.bars[-min(10, len(frame.bars)) :]
        if not recent:
            return LayerCheck("displacement", False, ("no-bars",))
        body_moves = [abs(bar.close - bar.open) for bar in recent]
        wicks = [bar.high - bar.low for bar in recent]
        passed = mean(body_moves) >= mean(wicks) * 0.25
        return LayerCheck("displacement", passed, (f"body={mean(body_moves):.6f}", f"wick={mean(wicks):.6f}"))

    def _order_block(self, candidate: ZoneCandidate, frame: FrameAnalysis) -> LayerCheck:
        width = candidate.width
        passed = width <= max(frame.volatility * 10, abs(candidate.midpoint) * 0.02)
        return LayerCheck("order_block", passed, (f"width={width:.6f}", f"volatility={frame.volatility:.6f}"))

    def _fair_value_gap(self, candidate: ZoneCandidate, frame: FrameAnalysis) -> LayerCheck:
        recent = frame.bars[-3:]
        if len(recent) < 3:
            return LayerCheck("fair_value_gap", False, ("too-few-bars",))
        gap = recent[-1].low - recent[-3].high if candidate.side is ZoneSide.BUY else recent[-3].low - recent[-1].high
        passed = abs(gap) > 0
        return LayerCheck("fair_value_gap", passed, (f"gap={gap:.6f}",))

    def _structure(self, candidate: ZoneCandidate, frame: FrameAnalysis) -> LayerCheck:
        passed = (candidate.side is ZoneSide.BUY and frame.trend != "down") or (candidate.side is ZoneSide.SELL and frame.trend != "up")
        return LayerCheck("structure", passed, (f"trend={frame.trend}",))

    def _premium_discount(self, candidate: ZoneCandidate, frame: FrameAnalysis, higher: tuple[FrameAnalysis, ...]) -> LayerCheck:
        closes = [bar.close for bar in frame.bars]
        if not closes:
            return LayerCheck("premium_discount", False, ("no-closes",))
        low = min(closes)
        high = max(closes)
        mid = (low + high) / 2.0
        passed = candidate.midpoint <= mid if candidate.side is ZoneSide.BUY else candidate.midpoint >= mid
        return LayerCheck("premium_discount", passed, (f"mid={mid:.6f}", f"midpoint={candidate.midpoint:.6f}"))

    def _internal_liquidity(self, candidate: ZoneCandidate, frame: FrameAnalysis) -> LayerCheck:
        passed = len(frame.bars) >= 5 and len(frame.swing_highs) + len(frame.swing_lows) >= 2
        return LayerCheck("internal_liquidity", passed, (f"bars={len(frame.bars)}",))

    def _liquidity_sweep(self, candidate: ZoneCandidate, frame: FrameAnalysis) -> LayerCheck:
        recent = frame.bars[-5:]
        if not recent:
            return LayerCheck("liquidity_sweep", False, ("no-recent-bars",))
        high = max(bar.high for bar in recent)
        low = min(bar.low for bar in recent)
        passed = (candidate.side is ZoneSide.BUY and low <= candidate.lower) or (candidate.side is ZoneSide.SELL and high >= candidate.upper)
        return LayerCheck("liquidity_sweep", passed, (f"recent_high={high:.6f}", f"recent_low={low:.6f}"))

    def _repricing(self, candidate: ZoneCandidate, frame: FrameAnalysis) -> LayerCheck:
        closes = [bar.close for bar in frame.bars[-6:]]
        passed = len(closes) >= 3 and closes[-1] != closes[0]
        return LayerCheck("repricing", passed, (f"first={closes[0] if closes else 0:.6f}", f"last={closes[-1] if closes else 0:.6f}"))

    def _order_flow(self, candidate: ZoneCandidate, frame: FrameAnalysis, higher: tuple[FrameAnalysis, ...]) -> LayerCheck:
        passed = not higher or all(h.trend in {frame.trend, "flat"} for h in higher)
        return LayerCheck("order_flow", passed, (f"higher_count={len(higher)}",))

    def _momentum(self, candidate: ZoneCandidate, frame: FrameAnalysis) -> LayerCheck:
        closes = [bar.close for bar in frame.bars[-8:]]
        if len(closes) < 4:
            return LayerCheck("momentum", False, ("too-few-closes",))
        diff = closes[-1] - closes[0]
        passed = (candidate.side is ZoneSide.BUY and diff >= 0) or (candidate.side is ZoneSide.SELL and diff <= 0)
        return LayerCheck("momentum", passed, (f"diff={diff:.6f}",))

    def _execution_path(self, candidate: ZoneCandidate, frame: FrameAnalysis, higher: tuple[FrameAnalysis, ...]) -> LayerCheck:
        passed = all(abs(frame.volatility - h.volatility) < max(frame.volatility, h.volatility, 1e-6) * 4 for h in higher) if higher else True
        return LayerCheck("execution_path", passed, (f"higher_count={len(higher)}",))

    def _stop_loss_safety(self, candidate: ZoneCandidate, frame: FrameAnalysis) -> LayerCheck:
        span = candidate.width
        passed = span > 0 and span <= max(frame.volatility * 12, abs(candidate.midpoint) * 0.05)
        return LayerCheck("stop_loss_safety", passed, (f"span={span:.6f}",))

    def _risk_reward(self, candidate: ZoneCandidate, frame: FrameAnalysis) -> LayerCheck:
        rr = max(candidate.score / 50.0, 0.0)
        passed = rr >= 1.0
        return LayerCheck("risk_reward", passed, (f"rr={rr:.6f}",))

    def _higher_timeframe_confluence(self, candidate: ZoneCandidate, frame: FrameAnalysis, higher: tuple[FrameAnalysis, ...]) -> LayerCheck:
        if not higher:
            return LayerCheck("higher_timeframe_confluence", True, ("no-higher-timeframes",))
        passed = all((candidate.side is ZoneSide.BUY and h.trend != "down") or (candidate.side is ZoneSide.SELL and h.trend != "up") for h in higher)
        return LayerCheck("higher_timeframe_confluence", passed, (f"higher_count={len(higher)}",))

    def _absolute_market_maker_confluence(self, candidate: ZoneCandidate, frame: FrameAnalysis, higher: tuple[FrameAnalysis, ...]) -> LayerCheck:
        passed = self._liquidity_intent(candidate, frame, AnalysisStrategyProfile(name="x")).passed and self._structure(candidate, frame).passed and self._risk_reward(candidate, frame).passed
        return LayerCheck("absolute_market_maker_confluence", passed, ("composite=true",))
