from __future__ import annotations

import logging
from pathlib import Path

from supreme_zone.core import bootstrap as bootstrap_module


class _DummySettings:
    app_name = "Supreme Zone Platform"
    log_level = "INFO"

    class storage:
        logs = Path("storage/logs")


class _DummySettingsManager:
    config_path = Path("config/default.yaml")

    def load(self) -> _DummySettings:
        return _DummySettings()


class _DummyErrorHandler:
    def __init__(self, logger, error_log_path=None):
        self.logger = logger
        self.error_log_path = error_log_path

    def handle_exception(self, exc, context="runtime"):
        raise exc


def test_bootstrap_creates_runtime_dirs(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(bootstrap_module, "SettingsManager", _DummySettingsManager)
    monkeypatch.setattr(bootstrap_module, "ErrorHandler", _DummyErrorHandler)
    monkeypatch.setattr(bootstrap_module, "configure_logging", lambda level, log_dir=None: logging.getLogger("test-bootstrap"))

    result = bootstrap_module.bootstrap()

    assert result.ready is True
    assert result.app_name == "Supreme Zone Platform"
    assert result.config_path == Path("config/default.yaml")
    assert result.storage_root == Path("storage")
    assert "ErrorHandler" in result.services_registered

    for folder in ["storage/charts", "storage/ohlc", "storage/reports", "storage/logs", "storage/cache", "storage/database"]:
        assert (tmp_path / folder).exists()
