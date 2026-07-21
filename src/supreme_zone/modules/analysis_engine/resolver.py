from __future__ import annotations

from dataclasses import dataclass

from .models import FrameAnalysis, ZoneCandidate, ZoneSide


@dataclass(slots=True)
class ZoneResolver:
    def resolve(self, analyses: tuple[FrameAnalysis, ...]) -> tuple[ZoneCandidate | None, ZoneCandidate | None]:
        buys = [analysis.buy_candidate for analysis in analyses if analysis.buy_candidate is not None]
        sells = [analysis.sell_candidate for analysis in analyses if analysis.sell_candidate is not None]
        return self._best(buys, ZoneSide.BUY), self._best(sells, ZoneSide.SELL)

    def _best(self, candidates: list[ZoneCandidate], side: ZoneSide) -> ZoneCandidate | None:
        if not candidates:
            return None
        ordered = sorted(
            candidates,
            key=lambda candidate: (
                -candidate.score,
                candidate.timeframe,
                candidate.lower,
                candidate.upper,
                candidate.source,
            ),
        )
        return ordered[0]
