from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ...core.error_handler import ErrorHandler
from ...core.settings import Settings
from .accounts import MT5AccountManager, MT5AccountProfile
from .cache import MarketCache
from .chart_renderer import ChartRenderer
from .database import MarketDatabase
from .errors import DataConnectionError, DataSyncError
from .market import MarketBar
from .models import MT5Credentials, MarketDataRequest
from .mt5_connector import MT5Connector
from .providers import MT5MarketDataProvider, TwelveDataMarketDataProvider
from .scheduler import UpdateScheduler
from .storage import MarketStorage
from .symbol_manager import SymbolManager
from .timeframe_manager import TimeframeManager


_DEFAULT_TWELVE_DATA_BASE_URL = "https://api.twelvedata.com/time_series"
_INVALID_API_KEY_MARKERS = {"", "***", "present", "missing", "none", "null"}


@dataclass(slots=True)
class DataEngineStatus:
    mt5_connected: bool = False
    active_account: str | None = None
    connected_accounts: tuple[str, ...] = ()
    last_symbol: str | None = None
    last_timeframe: str | None = None
    last_ohlc_path: Path | None = None
    last_chart_path: Path | None = None
    last_sync_count: int = 0
    data_source: str = "mt5"


class DataEngine:
    def __init__(
        self,
        settings: Settings,
        storage: MarketStorage | None = None,
        renderer: ChartRenderer | None = None,
        symbol_manager: SymbolManager | None = None,
        timeframe_manager: TimeframeManager | None = None,
        cache: MarketCache | None = None,
        database: MarketDatabase | None = None,
        account_manager: MT5AccountManager | None = None,
        scheduler: UpdateScheduler | None = None,
        error_handler: ErrorHandler | None = None,
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
        self.cache = cache or MarketCache(ttl_seconds=max(settings.market.live_poll_interval_seconds, 1))
        self.database = database or MarketDatabase(path=settings.storage.database / "market.sqlite3")
        self.account_manager = account_manager or MT5AccountManager()
        self.scheduler = scheduler or UpdateScheduler(interval_seconds=settings.market.live_poll_interval_seconds)
        self.error_handler = error_handler
        self.status = DataEngineStatus()
        self._connector: MT5Connector | None = None
        self._connectors: dict[str, MT5Connector] = {}
        self._twelve_data_provider: TwelveDataMarketDataProvider | None = None
        self.data_source = os.getenv("SUPREME_DATA_SOURCE", "mt5").strip().lower() or "mt5"
        if self.data_source not in {"mt5", "twelve_data"}:
            self.data_source = "mt5"
        self.twelve_data_api_key = os.getenv("TWELVE_DATA_API_KEY", "").strip()
        self.twelve_data_base_url = self._normalize_base_url(os.getenv("TWELVE_DATA_BASE_URL", _DEFAULT_TWELVE_DATA_BASE_URL))

        self.symbol_manager.load(settings.symbols)
        self.timeframe_manager.load(settings.timeframes)
        self.storage.ensure()
        self.database.initialize()
        self._load_accounts_from_settings()

    @staticmethod
    def _normalize_base_url(base_url: str | None) -> str:
        value = str(base_url or "").strip()
        if not value:
            return _DEFAULT_TWELVE_DATA_BASE_URL
        if not value.startswith(("http://", "https://")):
            return _DEFAULT_TWELVE_DATA_BASE_URL
        return value.rstrip("?&")

    def set_data_source(self, source: str, api_key: str | None = None, base_url: str | None = None) -> None:
        self.data_source = str(source).strip().lower() or "mt5"
        if self.data_source not in {"mt5", "twelve_data"}:
            self.data_source = "mt5"
        if api_key is not None:
            cleaned_api_key = api_key.strip()
            if cleaned_api_key.lower() not in _INVALID_API_KEY_MARKERS:
                self.twelve_data_api_key = cleaned_api_key
        if base_url is not None:
            self.twelve_data_base_url = self._normalize_base_url(base_url)
        self.status.data_source = self.data_source
        self._twelve_data_provider = None

    def _load_accounts_from_settings(self) -> None:
        mt5 = self.settings.mt5
        profiles: list[MT5AccountProfile] = []
        if mt5.accounts:
            profiles.extend(
                MT5AccountProfile(
                    label=account.label,
                    server=account.server or mt5.server or "",
                    login=account.login or 0,
                    password=account.password or "",
                )
                for account in mt5.accounts
                if account.server is not None and account.login is not None and account.password is not None
            )
        elif mt5.server is not None and mt5.login is not None and mt5.password is not None:
            profiles.append(
                MT5AccountProfile(
                    label="primary",
                    server=mt5.server,
                    login=mt5.login,
                    password=mt5.password,
                )
            )
        self.account_manager.load(profiles)
        self.status.active_account = self.account_manager.active().label if self.account_manager.active() else None

    def build_mt5_connector(self, account_label: str | None = None) -> MT5Connector:
        mt5 = self.settings.mt5
        if not mt5.enabled:
            raise DataConnectionError("MT5 integration is disabled in settings")

        account = None
        if account_label is not None:
            for item in self.account_manager.accounts:
                if item.label == account_label:
                    account = item
                    break
            if account is None:
                raise DataConnectionError(f"Unknown MT5 account: {account_label}")
        else:
            account = self.account_manager.active() or mt5.primary_account

        if account is None or not account.is_complete:
            raise DataConnectionError("MT5 credentials are incomplete")

        credentials = MT5Credentials(server=account.server or "", login=account.login or 0, password=account.password or "")
        connector = MT5Connector(credentials=credentials, terminal_path=mt5.terminal_path)
        label = account.label if account_label is None else account_label
        self._connectors[label] = connector
        if self._connector is None:
            self._connector = connector
        return connector

    def _connector_for_account(self, account_label: str | None = None) -> MT5Connector:
        connector = None
        if account_label is not None:
            connector = self._connectors.get(account_label)
            if connector is None:
                connector = self.build_mt5_connector(account_label)
        else:
            active = self.account_manager.active()
            if active is not None:
                connector = self._connectors.get(active.label)
            connector = connector or self._connector
            if connector is None:
                connector = self.build_mt5_connector()
        if connector is None:
            raise DataConnectionError("MT5 connector is unavailable")
        if not connector.is_connected():
            if not connector.connect():
                raise DataConnectionError("MT5 connector reconnect failed")
            self.status.mt5_connected = True
        return connector

    def connect_mt5(self, account_label: str | None = None) -> bool:
        connector = self._connector_for_account(account_label)
        connected = connector.connect()
        self.status.mt5_connected = connected
        if account_label is not None:
            self.status.active_account = account_label
        elif self.account_manager.active() is not None:
            self.status.active_account = self.account_manager.active().label
        return connected

    def connect_all_accounts(self) -> dict[str, bool]:
        results: dict[str, bool] = {}
        for account in self.account_manager.accounts:
            connector = self.build_mt5_connector(account.label)
            results[account.label] = connector.connect()
        self.status.connected_accounts = tuple(label for label, ok in results.items() if ok)
        self.status.mt5_connected = any(results.values())
        return results

    def reconnect_mt5(self, account_label: str | None = None) -> bool:
        connector = self._connector_for_account(account_label)
        connector.shutdown()
        return connector.connect()

    def _market_provider(self):
        if self.data_source == "twelve_data":
            if self._twelve_data_provider is None:
                self._twelve_data_provider = TwelveDataMarketDataProvider(
                    api_key=self.twelve_data_api_key,
                    base_url=self.twelve_data_base_url,
                )
            else:
                self._twelve_data_provider.api_key = self.twelve_data_api_key
                self._twelve_data_provider.base_url = self.twelve_data_base_url
            return self._twelve_data_provider
        return None

    def _cache_key(self, symbol: str, timeframe: str, bars: int) -> str:
        return f"ohlc:{symbol.upper().strip()}:{timeframe.upper().strip()}:{bars}"

    def fetch_ohlc(
        self,
        symbol: str,
        timeframe: str,
        bars: int | None = None,
        use_cache: bool = True,
        force_refresh: bool = False,
    ) -> list[MarketBar]:
        normalized_symbol = symbol.upper().strip()
        normalized_timeframe = self.timeframe_manager.normalize(timeframe)
        requested_bars = max(int(bars or self.settings.market.history_window_candles), self.settings.minimum_candles)
        cache_key = self._cache_key(normalized_symbol, normalized_timeframe, requested_bars)

        if use_cache and not force_refresh:
            cached = self.cache.get(cache_key)
            if cached is not None:
                return [bar if isinstance(bar, MarketBar) else MarketBar.from_mapping(bar) for bar in cached]

        request = MarketDataRequest(symbol=normalized_symbol, timeframe=normalized_timeframe, bars=requested_bars)
        if self.data_source == "twelve_data":
            provider = self._market_provider()
            if provider is None:
                raise DataConnectionError("Twelve Data provider is unavailable")
            raw_bars = provider.fetch_rates(request)
        else:
            connector = self._connector_or_fail()
            raw_bars = connector.fetch_rates(request)

        market_bars = [MarketBar.from_mapping(item) for item in raw_bars]
        self.status.data_source = self.data_source
        self.status.last_symbol = normalized_symbol
        self.status.last_timeframe = normalized_timeframe
        self.status.last_ohlc_path = self.storage.save_ohlc(normalized_symbol, normalized_timeframe, market_bars)
        self.database.upsert_bars(normalized_symbol, normalized_timeframe, market_bars)
        self.cache.set(cache_key, market_bars)
        self.status.last_sync_count = len(market_bars)
        return market_bars

    def render_chart(self, symbol: str, timeframe: str, bars: list[MarketBar]) -> Path:
        path = self.storage.chart_path(symbol, timeframe)
        rendered = self.renderer.render(bars, path, title=f"{symbol.upper()} {timeframe.upper()}")
        self.status.last_chart_path = rendered
        self.database.record_chart(symbol, timeframe, rendered)
        return rendered

    def sync_market(
        self,
        symbol: str,
        timeframe: str,
        bars: int | None = None,
        use_cache: bool = True,
        force_refresh: bool = False,
    ) -> dict[str, Any]:
        try:
            market_bars = self.fetch_ohlc(symbol, timeframe, bars=bars, use_cache=use_cache, force_refresh=force_refresh)
            if len(market_bars) < self.settings.minimum_candles:
                raise DataSyncError(
                    f"Insufficient OHLC bars for {symbol} {timeframe}: {len(market_bars)} < {self.settings.minimum_candles}"
                )
            chart_path = self.render_chart(symbol, timeframe, market_bars)
            self.database.record_sync_run(symbol, timeframe, len(market_bars), status="ok")
            return {
                "symbol": symbol.upper().strip(),
                "timeframe": self.timeframe_manager.normalize(timeframe),
                "bars": len(market_bars),
                "ohlc_path": self.status.last_ohlc_path,
                "chart_path": chart_path,
                "cached": use_cache and not force_refresh,
                "data_source": self.data_source,
            }
        except Exception as exc:
            self.database.record_error("sync_market", str(exc))
            if self.error_handler is not None:
                self.error_handler.handle_exception(exc, context="data-sync")
            raise DataSyncError(f"Failed to sync {symbol} {timeframe}") from exc

    def sync_all(self, bars: int | None = None, use_cache: bool = True, force_refresh: bool = False) -> list[dict[str, Any]]:
        if not self.symbol_manager.symbols:
            return []
        results: list[dict[str, Any]] = []
        for symbol in self.symbol_manager.symbols:
            for timeframe in self.timeframe_manager.supported:
                try:
                    results.append(
                        self.sync_market(
                            symbol,
                            timeframe,
                            bars=bars,
                            use_cache=use_cache,
                            force_refresh=force_refresh,
                        )
                    )
                except Exception as exc:
                    self.database.record_sync_run(
                        symbol,
                        timeframe,
                        0,
                        status="error",
                        details={"error": str(exc), "data_source": self.data_source},
                    )
                    results.append(
                        {
                            "symbol": symbol.upper().strip(),
                            "timeframe": self.timeframe_manager.normalize(timeframe),
                            "status": "error",
                            "error": str(exc),
                            "data_source": self.data_source,
                        }
                    )
        return results

    def create_live_stream(self, interval_seconds: int | None = None):
        from .live_stream import LiveDataStream

        return LiveDataStream(
            engine=self,
            interval_seconds=interval_seconds or self.settings.market.live_poll_interval_seconds,
            error_handler=self.error_handler,
        )

    def create_scheduler_job(self, name: str = "market-sync", bars: int | None = None) -> None:
        def job() -> Any:
            if self.data_source == "mt5" and not self.status.mt5_connected:
                self.connect_mt5()
            return self.sync_all(bars=bars)

        self.scheduler.register(name, job)

    def start_scheduler(self) -> None:
        self.scheduler.start()

    def stop_scheduler(self) -> None:
        self.scheduler.stop()

    def disconnect(self) -> None:
        if self._connector is not None:
            self._connector.shutdown()
        for connector in self._connectors.values():
            connector.shutdown()
        self.status.mt5_connected = False