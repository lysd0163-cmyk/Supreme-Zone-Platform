from __future__ import annotations

from datetime import datetime
from pathlib import Path

from supreme_zone.modules.data_engine.cache import MarketCache
from supreme_zone.modules.data_engine.database import MarketDatabase
from supreme_zone.modules.data_engine.market import MarketBar


def test_market_cache_respects_ttl() -> None:
    cache = MarketCache(ttl_seconds=1)
    cache.set("key", 123)
    assert cache.get("key") == 123
    assert cache.contains("key") is True


def test_market_database_persists_bars(tmp_path) -> None:
    database = MarketDatabase(path=tmp_path / "market.sqlite3")
    database.initialize()

    bars = [
        MarketBar(
            time=datetime(2026, 1, 1, 0, 0),
            open=1.0,
            high=1.1,
            low=0.9,
            close=1.05,
            tick_volume=100,
        )
    ]

    inserted = database.upsert_bars("EURUSD", "M15", bars)
    assert inserted == 1
    loaded = database.load_bars("EURUSD", "M15", limit=10)
    assert len(loaded) == 1
    assert loaded[0]["symbol"] == "EURUSD"
    database.record_chart("EURUSD", "M15", Path("chart.png"))
    database.record_sync_run("EURUSD", "M15", 1, status="ok")
    database.record_error("sync_market", "boom")
