from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .exceptions import ConfigurationError


@dataclass(slots=True, frozen=True)
class AppSettings:
    name: str = "Supreme Zone Platform"
    environment: str = "development"
    log_level: str = "INFO"
    timezone: str = "Asia/Baghdad"


@dataclass(slots=True, frozen=True)
class MarketSettings:
    symbols: tuple[str, ...] = ()
    timeframes: tuple[str, ...] = ("D1", "H4", "H1", "M15")
    minimum_candles: int = 500
    live_poll_interval_seconds: int = 60
    history_window_candles: int = 500


@dataclass(slots=True, frozen=True)
class StrategySettings:
    active: str | None = None
    directory: str = "strategies"
    allowed_extensions: tuple[str, ...] = (".yaml", ".yml", ".json", ".md", ".txt", ".pdf")
    require_signature: bool = False
    versioning_enabled: bool = True


@dataclass(slots=True, frozen=True)
class StorageSettings:
    root: Path = Path("storage")
    charts: Path = Path("storage/charts")
    ohlc: Path = Path("storage/ohlc")
    reports: Path = Path("storage/reports")
    logs: Path = Path("storage/logs")
    cache: Path = Path("storage/cache")
    database: Path = Path("storage/database")

    def directories(self) -> tuple[Path, ...]:
        return (self.charts, self.ohlc, self.reports, self.logs, self.cache, self.database)


@dataclass(slots=True, frozen=True)
class ExecutionSettings:
    enabled: bool = False
    broker: str = "MetaTrader"
    auto_trade: bool = False
    lot_size: float = 0.01
    max_open_positions: int = 1


@dataclass(slots=True, frozen=True)
class MT5AccountSettings:
    label: str = "default"
    server: str | None = None
    login: int | None = None
    password: str | None = None

    @property
    def is_complete(self) -> bool:
        return self.server is not None and self.login is not None and self.password is not None


@dataclass(slots=True, frozen=True)
class MT5Settings:
    enabled: bool = False
    terminal_path: str | None = None
    server: str | None = None
    login: int | None = None
    password: str | None = None
    accounts: tuple[MT5AccountSettings, ...] = ()

    @property
    def primary_account(self) -> MT5AccountSettings:
        if self.accounts:
            return self.accounts[0]
        return MT5AccountSettings(server=self.server, login=self.login, password=self.password)

    @property
    def has_accounts(self) -> bool:
        return bool(self.accounts)


@dataclass(slots=True, frozen=True)
class MonitoringSettings:
    enabled: bool = True
    refresh_interval_seconds: int = 60
    reanalyse_on_invalidated_zone: bool = True


@dataclass(slots=True, frozen=True)
class Settings:
    app: AppSettings = field(default_factory=AppSettings)
    market: MarketSettings = field(default_factory=MarketSettings)
    strategy: StrategySettings = field(default_factory=StrategySettings)
    storage: StorageSettings = field(default_factory=StorageSettings)
    execution: ExecutionSettings = field(default_factory=ExecutionSettings)
    mt5: MT5Settings = field(default_factory=MT5Settings)
    monitoring: MonitoringSettings = field(default_factory=MonitoringSettings)

    @property
    def app_name(self) -> str:
        return self.app.name

    @property
    def log_level(self) -> str:
        return self.app.log_level

    @property
    def minimum_candles(self) -> int:
        return self.market.minimum_candles

    @property
    def symbols(self) -> tuple[str, ...]:
        return self.market.symbols

    @property
    def timeframes(self) -> tuple[str, ...]:
        return self.market.timeframes


class SettingsManager:
    def __init__(self, config_path: str | Path = "config/default.yaml") -> None:
        self.config_path = Path(config_path)

    def load(self) -> Settings:
        if not self.config_path.exists():
            raise ConfigurationError(f"Configuration file not found: {self.config_path}")
        try:
            raw = yaml.safe_load(self.config_path.read_text(encoding="utf-8")) or {}
        except Exception as exc:
            raise ConfigurationError(f"Failed to load configuration: {exc}") from exc

        if not isinstance(raw, dict):
            raise ConfigurationError("Configuration root must be a mapping")

        return Settings(
            app=self._build_app(raw.get("app", {})),
            market=self._build_market(raw.get("market", {})),
            strategy=self._build_strategy(raw.get("strategy", {})),
            storage=self._build_storage(raw.get("storage", {})),
            execution=self._build_execution(raw.get("execution", {})),
            mt5=self._build_mt5(raw.get("mt5", {})),
            monitoring=self._build_monitoring(raw.get("monitoring", {})),
        )

    @staticmethod
    def _build_app(section: Any) -> AppSettings:
        data = section if isinstance(section, dict) else {}
        return AppSettings(
            name=str(data.get("name", AppSettings.name)),
            environment=str(data.get("environment", AppSettings.environment)),
            log_level=str(data.get("log_level", AppSettings.log_level)),
            timezone=str(data.get("timezone", AppSettings.timezone)),
        )

    @staticmethod
    def _build_market(section: Any) -> MarketSettings:
        data = section if isinstance(section, dict) else {}
        symbols = tuple(str(item) for item in data.get("symbols", ()) if item is not None)
        timeframes = tuple(str(item) for item in data.get("timeframes", MarketSettings.timeframes) if item is not None)
        return MarketSettings(
            symbols=symbols,
            timeframes=timeframes or MarketSettings.timeframes,
            minimum_candles=int(data.get("minimum_candles", MarketSettings.minimum_candles)),
            live_poll_interval_seconds=int(data.get("live_poll_interval_seconds", MarketSettings.live_poll_interval_seconds)),
            history_window_candles=int(data.get("history_window_candles", MarketSettings.history_window_candles)),
        )

    @staticmethod
    def _build_strategy(section: Any) -> StrategySettings:
        data = section if isinstance(section, dict) else {}
        allowed = tuple(str(item) for item in data.get("allowed_extensions", StrategySettings.allowed_extensions) if item is not None)
        active = data.get("active")
        return StrategySettings(
            active=str(active) if active not in (None, "") else None,
            directory=str(data.get("directory", StrategySettings.directory)),
            allowed_extensions=allowed or StrategySettings.allowed_extensions,
            require_signature=bool(data.get("require_signature", StrategySettings.require_signature)),
            versioning_enabled=bool(data.get("versioning_enabled", StrategySettings.versioning_enabled)),
        )

    @staticmethod
    def _build_storage(section: Any) -> StorageSettings:
        data = section if isinstance(section, dict) else {}
        return StorageSettings(
            root=Path(data.get("root", StorageSettings.root)),
            charts=Path(data.get("charts", StorageSettings.charts)),
            ohlc=Path(data.get("ohlc", StorageSettings.ohlc)),
            reports=Path(data.get("reports", StorageSettings.reports)),
            logs=Path(data.get("logs", StorageSettings.logs)),
            cache=Path(data.get("cache", StorageSettings.cache)),
            database=Path(data.get("database", StorageSettings.database)),
        )

    @staticmethod
    def _build_execution(section: Any) -> ExecutionSettings:
        data = section if isinstance(section, dict) else {}
        return ExecutionSettings(
            enabled=bool(data.get("enabled", ExecutionSettings.enabled)),
            broker=str(data.get("broker", ExecutionSettings.broker)),
            auto_trade=bool(data.get("auto_trade", ExecutionSettings.auto_trade)),
            lot_size=float(data.get("lot_size", ExecutionSettings.lot_size)),
            max_open_positions=int(data.get("max_open_positions", ExecutionSettings.max_open_positions)),
        )

    @staticmethod
    def _build_mt5(section: Any) -> MT5Settings:
        data = section if isinstance(section, dict) else {}
        login = data.get("login")
        accounts_raw = data.get("accounts", ())
        accounts: list[MT5AccountSettings] = []
        if isinstance(accounts_raw, list):
            for index, item in enumerate(accounts_raw):
                account = item if isinstance(item, dict) else {}
                account_login = account.get("login")
                accounts.append(
                    MT5AccountSettings(
                        label=str(account.get("label", f"account_{index + 1}")),
                        server=str(account.get("server")) if account.get("server") not in (None, "") else None,
                        login=int(account_login) if account_login not in (None, "") else None,
                        password=str(account.get("password")) if account.get("password") not in (None, "") else None,
                    )
                )
        return MT5Settings(
            enabled=bool(data.get("enabled", MT5Settings.enabled)),
            terminal_path=str(data.get("terminal_path")) if data.get("terminal_path") not in (None, "") else None,
            server=str(data.get("server")) if data.get("server") not in (None, "") else None,
            login=int(login) if login not in (None, "") else None,
            password=str(data.get("password")) if data.get("password") not in (None, "") else None,
            accounts=tuple(accounts),
        )

    @staticmethod
    def _build_monitoring(section: Any) -> MonitoringSettings:
        data = section if isinstance(section, dict) else {}
        return MonitoringSettings(
            enabled=bool(data.get("enabled", MonitoringSettings.enabled)),
            refresh_interval_seconds=int(data.get("refresh_interval_seconds", MonitoringSettings.refresh_interval_seconds)),
            reanalyse_on_invalidated_zone=bool(data.get("reanalyse_on_invalidated_zone", MonitoringSettings.reanalyse_on_invalidated_zone)),
        )
