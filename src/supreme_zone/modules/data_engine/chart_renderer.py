from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .market import MarketBar


@dataclass(slots=True)
class ChartRenderer:
    style: str = "default"

    def render(self, bars: Iterable[MarketBar], output_path: Path, title: str | None = None) -> Path:
        bars_list = list(bars)
        if not bars_list:
            raise ValueError("Cannot render chart without bars")

        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.dates as mdates
            import matplotlib.pyplot as plt
            from matplotlib.patches import Rectangle
        except Exception as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("matplotlib is required for chart rendering") from exc

        output_path.parent.mkdir(parents=True, exist_ok=True)
        dates = [mdates.date2num(bar.time) for bar in bars_list]
        opens = [bar.open for bar in bars_list]
        highs = [bar.high for bar in bars_list]
        lows = [bar.low for bar in bars_list]
        closes = [bar.close for bar in bars_list]

        fig, ax = plt.subplots(figsize=(14, 8))
        width = 0.6 * (dates[1] - dates[0]) if len(dates) > 1 else 0.01

        for date, open_, high, low, close in zip(dates, opens, highs, lows, closes):
            color = "green" if close >= open_ else "red"
            ax.vlines(date, low, high, color=color, linewidth=1.0)
            lower = min(open_, close)
            height = abs(close - open_) or 0.0001
            rect = Rectangle((date - width / 2, lower), width, height, facecolor=color, edgecolor=color, alpha=0.8)
            ax.add_patch(rect)

        ax.xaxis_date()
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d %H:%M"))
        ax.set_xlabel("Time")
        ax.set_ylabel("Price")
        ax.set_title(title or "Market Chart")
        fig.autofmt_xdate()
        fig.tight_layout()
        fig.savefig(output_path, dpi=160)
        plt.close(fig)
        return output_path
