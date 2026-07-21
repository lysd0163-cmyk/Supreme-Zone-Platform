from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ...core.settings import MT5Settings, Settings
from .models import MT5Credentials, MarketDataRequest
from .mt5_connector import MT5Connector


@dataclass(slots=True)
class DataEngineStatus:
    mt5_connected: bool = False
    last_symbol: str | None = None
    last_timeframe: str | None = None


class DataEngine:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.status = DataEngineStatus()
        self._connector: MT5Connector | None = None

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

    def fetch_ohlc(self, symbol: str, timeframe: str, bars: int | None = None) -> list[dict[str, Any]]:
        connector = self._connector or self.build_mt5_connector()
        if not connector.is_connected():
            raise RuntimeError("MT5 connector is not connected")
        request = MarketDataRequest(symbol=symbol, timeframe=timeframe, bars=bars or self.settings.minimum_candles)
        self.status.last_symbol = symbol
        self.status.last_timeframe = timeframe
        return connector.fetch_rates(request)

    def disconnect(self) -> None:
        if self._connector is not None:
            self._connector.shutdown()
        self.status.mt5_connected = False
