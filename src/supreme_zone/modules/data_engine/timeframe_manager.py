from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class TimeframeManager:
    supported: tuple[str, ...] = field(default_factory=lambda: ("D1", "H4", "H1", "M15"))

    def load(self, timeframes: list[str] | tuple[str, ...] | None) -> None:
        items = tuple(str(item).upper().strip() for item in (timeframes or ()) if str(item).strip())
        self.supported = items or self.supported

    def contains(self, timeframe: str) -> bool:
        return timeframe.upper().strip() in self.supported

    def normalize(self, timeframe: str) -> str:
        value = timeframe.upper().strip()
        if not self.contains(value):
            raise ValueError(f"Unsupported timeframe: {timeframe}")
        return value
