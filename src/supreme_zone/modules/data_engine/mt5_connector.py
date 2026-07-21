from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .models import MT5Credentials, MarketDataRequest

try:  # pragma: no cover - optional dependency
    import MetaTrader5 as mt5
except Exception:  # pragma: no cover - optional dependency
    mt5 = None


@dataclass(slots=True)
class MT5ConnectionState:
    connected: bool = False
    account: int | None = None
    server: str | None = None


class MT5Connector:
    def __init__(self, credentials: MT5Credentials, terminal_path: str | None = None) -> None:
        self.credentials = credentials
        self.terminal_path = terminal_path
        self.state = MT5ConnectionState(connected=False, account=credentials.login, server=credentials.server)

    def connect(self) -> bool:
        if mt5 is None:
            raise RuntimeError("MetaTrader5 package is not installed")

        initialize_kwargs: dict[str, Any] = {}
        if self.terminal_path:
            initialize_kwargs["path"] = self.terminal_path

        if not mt5.initialize(**initialize_kwargs):
            return False

        authorized = mt5.login(
            login=self.credentials.login,
            password=self.credentials.password,
            server=self.credentials.server,
        )
        self.state.connected = bool(authorized)
        return self.state.connected

    def shutdown(self) -> None:
        if mt5 is not None:
            mt5.shutdown()
        self.state.connected = False

    def is_connected(self) -> bool:
        return self.state.connected

    def fetch_rates(self, request: MarketDataRequest) -> list[dict[str, Any]]:
        if mt5 is None:
            raise RuntimeError("MetaTrader5 package is not installed")
        if not self.state.connected:
            raise RuntimeError("MT5 connection is not established")

        timeframe = getattr(mt5, request.timeframe, None)
        if timeframe is None:
            raise ValueError(f"Unsupported timeframe: {request.timeframe}")

        rates = mt5.copy_rates_from_pos(request.symbol, timeframe, 0, request.bars)
        if rates is None:
            return []
        return [dict(item) for item in rates]
