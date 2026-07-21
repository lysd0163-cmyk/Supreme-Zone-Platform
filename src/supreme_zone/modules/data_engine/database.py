from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .market import MarketBar


@dataclass(slots=True)
class MarketDatabase:
    path: Path = Path("storage/database/market.sqlite3")

    def connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS market_bars (
                    symbol TEXT NOT NULL,
                    timeframe TEXT NOT NULL,
                    bar_time TEXT NOT NULL,
                    open REAL NOT NULL,
                    high REAL NOT NULL,
                    low REAL NOT NULL,
                    close REAL NOT NULL,
                    tick_volume INTEGER,
                    spread INTEGER,
                    real_volume INTEGER,
                    PRIMARY KEY (symbol, timeframe, bar_time)
                );

                CREATE TABLE IF NOT EXISTS sync_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    timeframe TEXT NOT NULL,
                    bars INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    details TEXT
                );

                CREATE TABLE IF NOT EXISTS charts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    timeframe TEXT NOT NULL,
                    chart_path TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS data_errors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    context TEXT NOT NULL,
                    message TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    details TEXT
                );
                """
            )

    def upsert_bars(self, symbol: str, timeframe: str, bars: Iterable[MarketBar]) -> int:
        payload = [
            (
                symbol.upper(),
                timeframe.upper(),
                bar.time.isoformat(),
                bar.open,
                bar.high,
                bar.low,
                bar.close,
                bar.tick_volume,
                bar.spread,
                bar.real_volume,
            )
            for bar in bars
        ]
        if not payload:
            return 0
        with self.connect() as connection:
            connection.executemany(
                """
                INSERT INTO market_bars (
                    symbol, timeframe, bar_time, open, high, low, close, tick_volume, spread, real_volume
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol, timeframe, bar_time) DO UPDATE SET
                    open=excluded.open,
                    high=excluded.high,
                    low=excluded.low,
                    close=excluded.close,
                    tick_volume=excluded.tick_volume,
                    spread=excluded.spread,
                    real_volume=excluded.real_volume
                """,
                payload,
            )
            return len(payload)

    def load_bars(self, symbol: str, timeframe: str, limit: int = 500) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT symbol, timeframe, bar_time, open, high, low, close, tick_volume, spread, real_volume
                FROM market_bars
                WHERE symbol = ? AND timeframe = ?
                ORDER BY bar_time DESC
                LIMIT ?
                """,
                (symbol.upper(), timeframe.upper(), limit),
            ).fetchall()
        result = [dict(row) for row in reversed(rows)]
        return result

    def record_chart(self, symbol: str, timeframe: str, chart_path: Path) -> None:
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO charts (symbol, timeframe, chart_path, created_at) VALUES (?, ?, ?, ?)",
                (symbol.upper(), timeframe.upper(), str(chart_path), datetime.now(timezone.utc).isoformat()),
            )

    def record_sync_run(self, symbol: str, timeframe: str, bars: int, status: str, details: dict[str, Any] | None = None) -> None:
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO sync_runs (symbol, timeframe, bars, created_at, status, details) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    symbol.upper(),
                    timeframe.upper(),
                    bars,
                    datetime.now(timezone.utc).isoformat(),
                    status,
                    json.dumps(details or {}, ensure_ascii=False),
                ),
            )

    def record_error(self, context: str, message: str, details: str | None = None) -> None:
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO data_errors (context, message, created_at, details) VALUES (?, ?, ?, ?)",
                (context, message, datetime.now(timezone.utc).isoformat(), details),
            )
