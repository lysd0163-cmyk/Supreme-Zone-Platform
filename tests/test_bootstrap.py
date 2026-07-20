from __future__ import annotations

import logging
from pathlib import Path

from supreme_zone.core import bootstrap as bootstrap_module


class _DummyConfig:
    app_name = "Supreme Zone Platform"
    log_level = "INFO"


class _DummyConfigManager:
    config_path = Path("config/default.yaml")

    def load(self) -> _DummyConfig:
        return _DummyConfig()


def test_bootstrap_creates_runtime_dirs(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(bootstrap_module, "ConfigManager", _DummyConfigManager)
    monkeypatch.setattr(bootstrap_module, "configure_logging", lambda level: logging.getLogger("test-bootstrap"))

    result = bootstrap_module.bootstrap()

    assert result.ready is True
    assert result.app_name == "Supreme Zone Platform"
    assert result.config_path == Path("config/default.yaml")
    assert result.storage_root == Path("storage")

    for folder in ["storage/charts", "storage/ohlc", "storage/reports", "storage/logs", "storage/cache", "storage/database"]:
        assert (tmp_path / folder).exists()
