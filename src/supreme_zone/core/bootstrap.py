from __future__ import annotations

import logging
from pathlib import Path

from .config import ConfigManager
from .container import ServiceContainer
from .events import EventBus
from .health import HealthMonitor
from .injector import DependencyInjector
from .logger import configure_logging
from .runtime import BootstrapResult


_REQUIRED_STORAGE_DIRS = (
    "storage/charts",
    "storage/ohlc",
    "storage/reports",
    "storage/logs",
    "storage/cache",
    "storage/database",
)


def bootstrap() -> BootstrapResult:
    config_manager = ConfigManager()
    config = config_manager.load()
    logger = configure_logging(level=config.log_level)

    logger.info("Bootstrapping %s", config.app_name)
    for folder in _REQUIRED_STORAGE_DIRS:
        Path(folder).mkdir(parents=True, exist_ok=True)

    container = ServiceContainer()
    event_bus = EventBus()
    health_monitor = HealthMonitor()
    injector = DependencyInjector(container)

    container.register_instance(ConfigManager, config_manager)
    container.register_instance(type(config), config)
    container.register_instance(logging.Logger, logger)
    container.register_instance(ServiceContainer, container)
    container.register_instance(EventBus, event_bus)
    container.register_instance(HealthMonitor, health_monitor)
    container.register_instance(DependencyInjector, injector)

    event_bus.publish("system.bootstrap.started", {"app_name": config.app_name})

    result = BootstrapResult(
        ready=True,
        app_name=config.app_name,
        config_path=config_manager.config_path,
        storage_root=Path("storage"),
        services_registered=(
            "ConfigManager",
            type(config).__name__,
            "Logger",
            "ServiceContainer",
            "EventBus",
            "HealthMonitor",
            "DependencyInjector",
        ),
    )

    event_bus.publish("system.bootstrap.ready", result)
    logger.info("Bootstrap complete: ready=%s", result.ready)
    return result
