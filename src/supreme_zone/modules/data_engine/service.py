from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ...core.settings import Settings
from .chart_renderer import ChartRenderer
from .market import MarketBar
from .models import MT5Credentials, MarketDataRequest
from .mt5_connector import MT5Connector
from .storage import MarketStorage
from .symbol_manager import SymbolManager
from .timeframe_manager import TimeframeManager


@dataclass(slots=True)
class DataEngineStatus:
    mt5_connected: bool = False
    last_symbol: str | None = None
    last_timeframe: str | None = None
    last_ohlc_path: Path | None = None
    last_chart_path: Path | None = None


class DataEngine:
    def __init__(
        self,
        settings: Settings,
        storage: MarketStorage | None = None,
        renderer: ChartRenderer | None = None,
        symbol_manager: SymbolManager | None = None,
        timeframe_manager: TimeframeManager | None = None,
    ) -> None:
        self.settings = settings
        self.storage = storage or MarketStorage(
            root=settings.storage.root,
            charts_dir=settings.storage.charts,
            ohlc_dir=settings.storage.ohlc,
        )
        self.renderer = renderer or ChartRenderer()
        self.symbol_manager = symbol_manager or SymbolManager()
        self.timeframe_manager = timeframe_manager or TimeframeManager()
        self.status = DataEngineStatus()
        self._connector: MT5Connector | None = None
        self.symbol_manager.load(settings.symbols)
        self.timeframe_manager.load(settings.timeframes)
        self.storage.ensure()

    def build_mt5_connector(self) -> MT5Connector:
        mt5 = self.settings.mt5
        if not mt5.enabled:
            raise RuntimeError("MT5 integration is disabled in settings")
        if mt5.server is None or mt5.login is None or mt5.password is None:
            raise RuntimeError("MT5 credentials are incomplete")
        credentials = MT5Credentials(server=mt5.server, login=mt5.login, password=mt5.password)
        self._connector = MT5Connector(credentials=credentials, terminal_path=mt5.terminal_path)
        return self._connector

    def connect_mt5(self) -> bool:
        connector = self._connector or self.build_mt5_connector()
        connected = connector.connect()
        self.status.mt5_connected = connected
        return connected

    def _connector_or_fail(self) -> MT5Connector:
        connector = self._connector or self.build_mt5_connector()
        if not connector.is_connected():
            raise RuntimeError("MT5 connector is not connected")
        return connector

    def fetch_ohlc(self, symbol: str, timeframe: str, bars: int | None = None) -> list[MarketBar]:
        connector = self._connector_or_fail()
        normalized_symbol = symbol.upper().strip()
        normalized_timeframe = self.timeframe_manager.normalize(timeframe)
        requested_bars = max(
            int(bars or self.settings.market.history_window_candles),
            self.settings.minimum_candles,
        )
        request = MarketDataRequest(symbol=normalized_symbol, timeframe=normalized_timeframe, bars=requested_bars)
        raw_bars = connector.fetch_rates(request)
        market_bars = [MarketBar.from_mapping(item) for item in raw_bars]

        self.status.last_symbol = normalized_symbol
        self.status.last_timeframe = normalized_timeframe
        self.status.last_ohlc_path = self.storage.save_ohlc(normalized_symbol, normalized_timeframe, market_bars)
        return market_bars

    def render_chart(self, symbol: str, timeframe: str, bars: list[MarketBar]) -> Path:
        path = self.storage.chart_path(symbol, timeframe)
        rendered = self.renderer.render(bars, path, title=f"{symbol.upper()} {timeframe.upper()}")
        self.status.last_chart_path = rendered
        return rendered

    def sync_market(self, symbol: str, timeframe: str, bars: int | None = None) -> dict[str, Any]:
        market_bars = self.fetch_ohlc(symbol, timeframe, bars=bars)
        chart_path = self.render_chart(symbol, timeframe, market_bars)
        return {
            "symbol": symbol.upper().strip(),
            "timeframe": self.timeframe_manager.normalize(timeframe),
            "bars": len(market_bars),
            "ohlc_path": self.status.last_ohlc_path,
            "chart_path": chart_path,
        }

    def sync_all(self, bars: int | None = None) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for symbol in self.symbol_manager.symbols:
            for timeframe in self.timeframe_manager.supported:
                results.append(self.sync_market(symbol, timeframe, bars=bars))
        return results

    def disconnect(self) -> None:
        if self._connector is not None:
            self._connector.shutdown()
        self.status.mt5_connected = False
