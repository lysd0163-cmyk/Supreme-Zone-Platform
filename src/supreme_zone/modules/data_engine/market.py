from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(slots=True, frozen=True)
class MarketBar:
    time: datetime
    open: float
    high: float
    low: float
    close: float
    tick_volume: int | None = None
    spread: int | None = None
    real_volume: int | None = None

    @classmethod
    def from_mapping(cls, mapping: dict[str, Any]) -> "MarketBar":
        raw_time = mapping.get("time")
        if isinstance(raw_time, datetime):
            parsed_time = raw_time
        elif isinstance(raw_time, (int, float)):
            parsed_time = datetime.fromtimestamp(raw_time)
        else:
            parsed_time = datetime.fromisoformat(str(raw_time))
        return cls(
            time=parsed_time,
            open=float(mapping.get("open", 0.0)),
            high=float(mapping.get("high", 0.0)),
            low=float(mapping.get("low", 0.0)),
            close=float(mapping.get("close", 0.0)),
            tick_volume=int(mapping.get("tick_volume", mapping.get("volume", 0)) or 0),
            spread=int(mapping.get("spread", 0) or 0),
            real_volume=int(mapping.get("real_volume", mapping.get("real_volume", 0)) or 0),
        )

    def to_mapping(self) -> dict[str, Any]:
        return {
            "time": self.time.isoformat(),
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "tick_volume": self.tick_volume,
            "spread": self.spread,
            "real_volume": self.real_volume,
        }
