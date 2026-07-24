from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .models import MT5Credentials, MarketDataRequest

try:  # pragma: no cover - optional dependency
    import MetaTrader5 as mt5
except Exception:  # pragma: no cover - optional dependency
    mt5 = None


_DEFAULT_TWELVE_DATA_BASE_URL = "https://api.twelvedata.com/time_series"
_INVALID_API_KEY_MARKERS = {"", "***", "present", "missing", "none", "null"}


class MarketDataProvider(Protocol):
    name: str

    def fetch_rates(self, request: MarketDataRequest) -> list[dict[str, object]]:
        ...


@dataclass(slots=True)
class MT5MarketDataProvider:
    credentials: MT5Credentials
    terminal_path: str | None = None
    name: str = "mt5"
    _connected: bool = False

    def connect(self) -> bool:
        if mt5 is None:
            raise RuntimeError("MetaTrader5 package is not installed")

        initialize_kwargs: dict[str, object] = {}
        if self.terminal_path:
            initialize_kwargs["path"] = self.terminal_path

        if not mt5.initialize(**initialize_kwargs):
            return False

        authorized = mt5.login(
            login=self.credentials.login,
            password=self.credentials.password,
            server=self.credentials.server,
        )
        self._connected = bool(authorized)
        return self._connected

    def shutdown(self) -> None:
        if mt5 is not None:
            mt5.shutdown()
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    def fetch_rates(self, request: MarketDataRequest) -> list[dict[str, object]]:
        if mt5 is None:
            raise RuntimeError("MetaTrader5 package is not installed")
        if not self._connected:
            raise RuntimeError("MT5 connection is not established")

        timeframe = getattr(mt5, request.timeframe, None)
        if timeframe is None:
            raise ValueError(f"Unsupported timeframe: {request.timeframe}")

        rates = mt5.copy_rates_from_pos(request.symbol, timeframe, 0, request.bars)
        if rates is None:
            return []
        return [dict(item) for item in rates]

    def place_market_order(self, symbol: str, volume: float, side: str, sl: float | None = None, tp: float | None = None, comment: str | None = None, magic: int | None = None) -> dict[str, object]:
        raise NotImplementedError


@dataclass(slots=True)
class TwelveDataMarketDataProvider:
    api_key: str
    base_url: str = _DEFAULT_TWELVE_DATA_BASE_URL
    name: str = "twelve_data"

    def fetch_rates(self, request: MarketDataRequest) -> list[dict[str, object]]:
        api_key = str(self.api_key or "").strip()
        if api_key.lower() in _INVALID_API_KEY_MARKERS:
            fallback = os.getenv("TWELVE_DATA_API_KEY", "").strip()
            if not fallback:
                raise RuntimeError("TWELVE_DATA_API_KEY is missing")
            api_key = fallback
            self.api_key = fallback

        interval = self._map_interval(request.timeframe)
        symbol = self._normalize_symbol(request.symbol)
        params = urlencode({
            "symbol": symbol,
            "interval": interval,
            "outputsize": str(request.bars),
            "format": "JSON",
            "apikey": api_key,
        })
        url = self._resolved_base_url()
        req = Request(f"{url}?{params}", headers={"User-Agent": "SupremeZonePlatform/0.1.0"})
        with urlopen(req, timeout=30) as response:  # nosec B310 - outbound API client
            payload = json.loads(response.read().decode("utf-8"))

        if isinstance(payload, dict) and str(payload.get("status", "")).lower() == "error":
            message = str(payload.get("message") or payload.get("code") or "unknown error")
            raise RuntimeError(f"Twelve Data returned an error for {symbol} {interval}: {message}")

        values = payload.get("values", []) if isinstance(payload, dict) else []
        bars: list[dict[str, object]] = []
        for item in reversed(values):
            bars.append(
                {
                    "time": self._parse_time(str(item.get("datetime") or item.get("date") or item.get("time") or datetime.now(timezone.utc).isoformat())),
                    "open": float(item.get("open", 0.0)),
                    "high": float(item.get("high", 0.0)),
                    "low": float(item.get("low", 0.0)),
                    "close": float(item.get("close", 0.0)),
                    "tick_volume": int(float(item.get("volume", item.get("tick_volume", 0)) or 0)),
                }
            )
        return bars

    def _resolved_base_url(self) -> str:
        candidate = str(self.base_url or "").strip()
        if not candidate:
            return _DEFAULT_TWELVE_DATA_BASE_URL
        if not candidate.startswith(("http://", "https://")):
            return _DEFAULT_TWELVE_DATA_BASE_URL
        return candidate.rstrip("?&")

    @staticmethod
    def _map_interval(timeframe: str) -> str:
        mapping = {
            "D1": "1day",
            "H4": "4h",
            "H1": "1h",
            "M15": "15min",
            "M5": "5min",
            "M30": "30min",
        }
        return mapping.get(timeframe.upper().strip(), timeframe.lower())

    @staticmethod
    def _normalize_symbol(symbol: str) -> str:
        normalized = symbol.upper().replace(" ", "").replace("/", "")
        if len(normalized) == 6:
            return f"{normalized[:3]}/{normalized[3:]}"
        return symbol.upper().replace(" ", "")

    @staticmethod
    def _parse_time(value: str) -> str:
        return value