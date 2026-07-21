from __future__ import annotations

from pathlib import Path

from .container import ServiceContainer
from .error_handler import ErrorHandler
from .events import EventBus
from .health import HealthMonitor
from .injector import DependencyInjector
from .logger import configure_logging
from .runtime import BootstrapResult
from .settings import Settings, SettingsManager
from ..modules.data_engine.accounts import MT5AccountManager
from ..modules.data_engine.cache import MarketCache
from ..modules.data_engine.database import MarketDatabase
from ..modules.data_engine.scheduler import UpdateScheduler
from ..modules.data_engine.service import DataEngine


_REQUIRED_STORAGE_DIRS = (
    "storage/charts",
    "storage/ohlc",
    "storage/reports",
    "storage/logs",
    "storage/cache",
    "storage/database",
)


def bootstrap() -> BootstrapResult:
    settings_manager = SettingsManager()
    settings = settings_manager.load()
    logger = configure_logging(level=settings.log_level, log_dir=settings.storage.logs)

    logger.info("Bootstrapping %s", settings.app_name)
    for folder in _REQUIRED_STORAGE_DIRS:
        Path(folder).mkdir(parents=True, exist_ok=True)

    container = ServiceContainer()
    event_bus = EventBus()
    health_monitor = HealthMonitor()
    injector = DependencyInjector(container)
    error_handler = ErrorHandler(logger, error_log_path=settings.storage.logs / "errors.jsonl")
    error_handler.install_global_hook()

    cache = MarketCache(ttl_seconds=max(settings.market.live_poll_interval_seconds, 1))
    database = MarketDatabase(path=settings.storage.database / "market.sqlite3")
    scheduler = UpdateScheduler(interval_seconds=settings.market.live_poll_interval_seconds)
    account_manager = MT5AccountManager()
    data_engine = DataEngine(
        settings,
        cache=cache,
        database=database,
        account_manager=account_manager,
        scheduler=scheduler,
        error_handler=error_handler,
    )

    container.register_instance(SettingsManager, settings_manager)
    container.register_instance(Settings, settings)
    container.register_instance(type(settings), settings)
    container.register_instance(type(logger), logger)
    container.register_instance(ServiceContainer, container)
    container.register_instance(EventBus, event_bus)
    container.register_instance(HealthMonitor, health_monitor)
    container.register_instance(DependencyInjector, injector)
    container.register_instance(ErrorHandler, error_handler)
    container.register_instance(MarketCache, cache)
    container.register_instance(MarketDatabase, database)
    container.register_instance(UpdateScheduler, scheduler)
    container.register_instance(MT5AccountManager, account_manager)
    container.register_instance(DataEngine, data_engine)

    event_bus.publish("system.bootstrap.started", {"app_name": settings.app_name})

    result = BootstrapResult(
        ready=True,
        app_name=settings.app_name,
        config_path=settings_manager.config_path,
        storage_root=Path("storage"),
        services_registered=(
            "SettingsManager",
            "Settings",
            "Logger",
            "ServiceContainer",
            "EventBus",
            "HealthMonitor",
            "DependencyInjector",
            "ErrorHandler",
            "MarketCache",
            "MarketDatabase",
            "UpdateScheduler",
            "MT5AccountManager",
            "DataEngine",
        ),
    )

    event_bus.publish("system.bootstrap.ready", result)
    logger.info("Bootstrap complete: ready=%s", result.ready)
    return result
