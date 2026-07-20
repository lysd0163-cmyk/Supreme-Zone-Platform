from __future__ import annotations

from pathlib import Path

from .config import ConfigManager
from .logger import configure_logging


def bootstrap() -> None:
    config = ConfigManager().load()
    logger = configure_logging(level=config.log_level)
    logger.info("Bootstrapping %s", config.app_name)

    for folder in ["storage/charts", "storage/ohlc", "storage/reports", "storage/logs", "storage/cache", "storage/database"]:
        Path(folder).mkdir(parents=True, exist_ok=True)

    logger.info("Bootstrap complete")
