from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .exceptions import ConfigurationError


@dataclass(slots=True)
class AppConfig:
    data: dict[str, Any] = field(default_factory=dict)

    @property
    def app_name(self) -> str:
        return str(self.data.get("app", {}).get("name", "Supreme Zone Platform"))

    @property
    def log_level(self) -> str:
        return str(self.data.get("app", {}).get("log_level", "INFO"))

    @property
    def minimum_candles(self) -> int:
        return int(self.data.get("market", {}).get("minimum_candles", 500))


class ConfigManager:
    def __init__(self, config_path: str | Path = "config/default.yaml") -> None:
        self.config_path = Path(config_path)

    def load(self) -> AppConfig:
        if not self.config_path.exists():
            raise ConfigurationError(f"Configuration file not found: {self.config_path}")
        try:
            raw = yaml.safe_load(self.config_path.read_text(encoding="utf-8")) or {}
        except Exception as exc:
            raise ConfigurationError(f"Failed to load configuration: {exc}") from exc
        if not isinstance(raw, dict):
            raise ConfigurationError("Configuration root must be a mapping")
        return AppConfig(data=raw)
