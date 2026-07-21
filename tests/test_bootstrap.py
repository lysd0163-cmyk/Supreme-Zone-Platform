from __future__ import annotations

import logging
from pathlib import Path

from supreme_zone.core import bootstrap as bootstrap_module


class _DummySettings:
    app_name = "Supreme Zone Platform"
    log_level = "INFO"

    class storage:
        root = Path("storage")
        charts = Path("storage/charts")
        ohlc = Path("storage/ohlc")
        reports = Path("storage/reports")
        logs = Path("storage/logs")
        cache = Path("storage/cache")
        database = Path("storage/database")

    class mt5:
        enabled = False
        terminal_path = None
        server = None
        login = None
        password = None

    @property
    def symbols(self) -> tuple[str, ...]:
        return ()

    @property
    def timeframes(self) -> tuple[str, ...]:
        return ("D1", "H4", "H1", "M15")


class _DummySettingsManager:
    config_path = Path("config/default.yaml")

    def load(self) -> _DummySettings:
        return _DummySettings()


class _DummyErrorHandler:
    def __init__(self, logger, error_log_path=None):
        self.logger = logger
        self.error_log_path = error_log_path

    def install_global_hook(self) -> None:
        return None

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
    assert "DataEngine" in result.services_registered

    for folder in ["storage/charts", "storage/ohlc", "storage/reports", "storage/logs", "storage/cache", "storage/database"]:
        assert (tmp_path / folder).exists()
