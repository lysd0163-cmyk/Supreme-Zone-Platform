from __future__ import annotations

from pathlib import Path

from .config import ConfigManager
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

    result = BootstrapResult(
        ready=True,
        app_name=config.app_name,
        config_path=config_manager.config_path,
        storage_root=Path("storage"),
    )
    logger.info("Bootstrap complete: ready=%s", result.ready)
    return result
