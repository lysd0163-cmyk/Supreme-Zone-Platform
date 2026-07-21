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

    def place_market_order(
        self,
        symbol: str,
        volume: float,
        side: str,
        sl: float | None = None,
        tp: float | None = None,
        comment: str | None = None,
        magic: int | None = None,
    ) -> dict[str, Any]:
        if mt5 is None:
            raise RuntimeError("MetaTrader5 package is not installed")
        if not self.state.connected:
            raise RuntimeError("MT5 connection is not established")

        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            raise RuntimeError(f"Unknown symbol: {symbol}")
        if not symbol_info.visible:
            mt5.symbol_select(symbol, True)

        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            raise RuntimeError(f"No market tick for symbol: {symbol}")

        side_normalized = side.upper().strip()
        if side_normalized == "BUY":
            order_type = mt5.ORDER_TYPE_BUY
            price = tick.ask
        elif side_normalized == "SELL":
            order_type = mt5.ORDER_TYPE_SELL
            price = tick.bid
        else:
            raise ValueError(f"Unsupported side: {side}")

        request: dict[str, Any] = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": float(volume),
            "type": order_type,
            "price": price,
            "deviation": 20,
            "magic": int(magic or 0),
            "comment": comment or "supreme-zone-platform",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_FOK,
        }
        if sl is not None:
            request["sl"] = float(sl)
        if tp is not None:
            request["tp"] = float(tp)

        result = mt5.order_send(request)
        if result is None:
            raise RuntimeError("MT5 order_send returned no result")
        return {
            "retcode": result.retcode,
            "order": getattr(result, "order", None),
            "deal": getattr(result, "deal", None),
            "comment": getattr(result, "comment", ""),
            "request": request,
        }

    def open_positions(self, symbol: str | None = None) -> list[dict[str, Any]]:
        if mt5 is None:
            raise RuntimeError("MetaTrader5 package is not installed")
        if not self.state.connected:
            raise RuntimeError("MT5 connection is not established")

        positions = mt5.positions_get(symbol=symbol) if symbol else mt5.positions_get()
        if positions is None:
            return []
        return [position._asdict() for position in positions]

    def close_position(self, ticket: int, symbol: str, volume: float, side: str, comment: str | None = None) -> dict[str, Any]:
        if mt5 is None:
            raise RuntimeError("MetaTrader5 package is not installed")
        if not self.state.connected:
            raise RuntimeError("MT5 connection is not established")

        side_normalized = side.upper().strip()
        if side_normalized == "BUY":
            close_type = mt5.ORDER_TYPE_SELL
        elif side_normalized == "SELL":
            close_type = mt5.ORDER_TYPE_BUY
        else:
            raise ValueError(f"Unsupported side: {side}")

        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            raise RuntimeError(f"No market tick for symbol: {symbol}")
        price = tick.bid if close_type == mt5.ORDER_TYPE_SELL else tick.ask

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "position": ticket,
            "volume": float(volume),
            "type": close_type,
            "price": price,
            "deviation": 20,
            "comment": comment or "supreme-zone-platform-close",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_FOK,
        }
        result = mt5.order_send(request)
        if result is None:
            raise RuntimeError("MT5 close order returned no result")
        return {
            "retcode": result.retcode,
            "order": getattr(result, "order", None),
            "deal": getattr(result, "deal", None),
            "comment": getattr(result, "comment", ""),
            "request": request,
        }
