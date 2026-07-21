from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Iterable

from ..data_engine.market import MarketBar
from .models import AnalysisStrategyProfile, FrameAnalysis, ZoneCandidate, ZoneSide, ChartImageSnapshot


@dataclass(slots=True)
class TimeframeAnalyzer:
    swing_window: int = 2

    def analyze(
        self,
        symbol: str,
        timeframe: str,
        bars: Iterable[MarketBar],
        profile: AnalysisStrategyProfile,
        image: ChartImageSnapshot | None = None,
    ) -> FrameAnalysis:
        bar_list = tuple(bars)
        if len(bar_list) < profile.minimum_candles:
            raise ValueError(
                f"Not enough OHLC bars for {symbol} {timeframe}: {len(bar_list)} < {profile.minimum_candles}"
            )

        closes = [bar.close for bar in bar_list]
        highs = [bar.high for bar in bar_list]
        lows = [bar.low for bar in bar_list]
        volatility = self._volatility(bar_list)
        trend = self._trend(closes)
        swing_highs, swing_lows = self._swings(bar_list)
        buy_candidate = self._candidate(symbol, timeframe, bar_list, trend, volatility, image, profile, ZoneSide.BUY, swing_lows, swing_highs)
        sell_candidate = self._candidate(symbol, timeframe, bar_list, trend, volatility, image, profile, ZoneSide.SELL, swing_highs, swing_lows)

        notes = [
            f"trend={trend}",
            f"volatility={volatility:.6f}",
            f"bars={len(bar_list)}",
        ]
        if profile.bias != "neutral":
            notes.append(f"strategy_bias={profile.bias}")

        return FrameAnalysis(
            symbol=symbol.upper().strip(),
            timeframe=timeframe.upper().strip(),
            bars=bar_list,
            image=image,
            trend=trend,
            volatility=volatility,
            buy_candidate=buy_candidate,
            sell_candidate=sell_candidate,
            swing_highs=swing_highs,
            swing_lows=swing_lows,
            notes=tuple(notes),
        )

    def _trend(self, closes: list[float]) -> str:
        if len(closes) < 3:
            return "flat"
        first = mean(closes[: max(3, len(closes) // 4)])
        last = mean(closes[-max(3, len(closes) // 4):])
        diff = last - first
        threshold = abs(first) * 0.001 if first else 0.0001
        if diff > threshold:
            return "up"
        if diff < -threshold:
            return "down"
        return "flat"

    def _volatility(self, bars: tuple[MarketBar, ...]) -> float:
        ranges = [max(bar.high - bar.low, 0.0) for bar in bars]
        return mean(ranges) if ranges else 0.0

    def _swings(self, bars: tuple[MarketBar, ...]) -> tuple[tuple[float, ...], tuple[float, ...]]:
        highs: list[float] = []
        lows: list[float] = []
        window = self.swing_window
        for index in range(window, len(bars) - window):
            segment = bars[index - window : index + window + 1]
            current = bars[index]
            if current.high == max(bar.high for bar in segment):
                highs.append(current.high)
            if current.low == min(bar.low for bar in segment):
                lows.append(current.low)
        return tuple(highs[-12:]), tuple(lows[-12:])

    def _candidate(
        self,
        symbol: str,
        timeframe: str,
        bars: tuple[MarketBar, ...],
        trend: str,
        volatility: float,
        image: ChartImageSnapshot | None,
        profile: AnalysisStrategyProfile,
        side: ZoneSide,
        pivots: tuple[float, ...],
        opposing_pivots: tuple[float, ...],
    ) -> ZoneCandidate | None:
        reference = pivots[-1] if pivots else (bars[-1].low if side is ZoneSide.BUY else bars[-1].high)
        recent_closes = [bar.close for bar in bars[-profile.lookback_bars :]]
        recent_high = max(bar.high for bar in bars[-profile.lookback_bars :])
        recent_low = min(bar.low for bar in bars[-profile.lookback_bars :])
        recent_range = max(recent_high - recent_low, volatility)
        width = max(recent_range * profile.zone_width_ratio, volatility * 1.5, abs(reference) * 0.0005)

        if side is ZoneSide.BUY:
            lower = reference
            upper = reference + width
            direction_bonus = 1.0 if trend in {"up", "flat"} else 0.5
            bias_bonus = 1.15 if profile.bias in {"buy", "bullish"} else 1.0
            pivot_bonus = 1.0 + min(len(pivots), 5) * 0.05
            recency_bonus = 1.15 if profile.prefer_recent and pivots else 1.0
            anchor = recent_low
            anchor_distance = max(reference - anchor, 0.0)
            evidence = [
                f"side=BUY",
                f"trend={trend}",
                f"reference_low={reference:.6f}",
                f"recent_low={anchor:.6f}",
                f"range={recent_range:.6f}",
                f"pivot_count={len(pivots)}",
            ]
            score = self._score(direction_bonus, bias_bonus, pivot_bonus, recency_bonus, image, anchor_distance, recent_range)
        else:
            upper = reference
            lower = reference - width
            direction_bonus = 1.0 if trend in {"down", "flat"} else 0.5
            bias_bonus = 1.15 if profile.bias in {"sell", "bearish"} else 1.0
            pivot_bonus = 1.0 + min(len(pivots), 5) * 0.05
            recency_bonus = 1.15 if profile.prefer_recent and pivots else 1.0
            anchor = recent_high
            anchor_distance = max(anchor - reference, 0.0)
            evidence = [
                f"side=SELL",
                f"trend={trend}",
                f"reference_high={reference:.6f}",
                f"recent_high={anchor:.6f}",
                f"range={recent_range:.6f}",
                f"pivot_count={len(pivots)}",
            ]
            score = self._score(direction_bonus, bias_bonus, pivot_bonus, recency_bonus, image, anchor_distance, recent_range)

        if opposing_pivots:
            evidence.append(f"opposing_pivots={len(opposing_pivots)}")
        if image is not None:
            evidence.extend(
                [
                    f"image_size={image.width}x{image.height}",
                    f"image_contrast={image.contrast:.2f}",
                ]
            )

        if upper <= lower:
            upper = lower + max(width, 0.0001)

        return ZoneCandidate(
            side=side,
            timeframe=timeframe.upper().strip(),
            symbol=symbol.upper().strip(),
            lower=float(lower),
            upper=float(upper),
            score=float(score),
            source="ohlc+image" if image is not None else "ohlc",
            evidence=tuple(evidence),
        )

    def _score(
        self,
        direction_bonus: float,
        bias_bonus: float,
        pivot_bonus: float,
        recency_bonus: float,
        image: ChartImageSnapshot | None,
        anchor_distance: float,
        recent_range: float,
    ) -> float:
        image_bonus = 1.0
        if image is not None:
            brightness_component = 1.0 + min(image.brightness / 255.0, 1.0) * 0.05
            contrast_component = 1.0 + min(image.contrast / 128.0, 1.0) * 0.05
            aspect_component = 1.0 + min(abs(image.aspect_ratio - 1.0), 1.0) * 0.02
            image_bonus = brightness_component * contrast_component * aspect_component
        distance_penalty = 1.0 / (1.0 + max(anchor_distance, 0.0) / max(recent_range, 1e-6))
        return round(100.0 * direction_bonus * bias_bonus * pivot_bonus * recency_bonus * image_bonus * distance_penalty, 4)
