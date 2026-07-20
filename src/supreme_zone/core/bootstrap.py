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

    container.register_instance(SettingsManager, settings_manager)
    container.register_instance(Settings, settings)
    container.register_instance(type(settings), settings)
    container.register_instance(type(logger), logger)
    container.register_instance(ServiceContainer, container)
    container.register_instance(EventBus, event_bus)
    container.register_instance(HealthMonitor, health_monitor)
    container.register_instance(DependencyInjector, injector)
    container.register_instance(ErrorHandler, error_handler)

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
        ),
    )

    event_bus.publish("system.bootstrap.ready", result)
    logger.info("Bootstrap complete: ready=%s", result.ready)
    return result
