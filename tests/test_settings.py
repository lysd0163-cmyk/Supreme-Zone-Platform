from __future__ import annotations

from pathlib import Path

from supreme_zone.core.settings import SettingsManager


def test_settings_manager_loads_default_configuration(tmp_path) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "default.yaml").write_text(
        """
app:
  name: Demo Platform
  log_level: DEBUG
market:
  symbols: [EURUSD, GBPUSD]
  timeframes: [D1, H4]
  minimum_candles: 700
storage:
  logs: demo-storage/logs
execution:
  enabled: true
mt5:
  enabled: true
  server: Demo-Server
  login: 12345
  password: secret
  accounts:
    - label: primary
      server: Demo-Server
      login: 12345
      password: secret
    - label: secondary
      server: Demo-Server-2
      login: 54321
      password: secret2
monitoring:
  enabled: false
""",
        encoding="utf-8",
    )

    settings = SettingsManager(config_dir / "default.yaml").load()

    assert settings.app_name == "Demo Platform"
    assert settings.log_level == "DEBUG"
    assert settings.minimum_candles == 700
    assert settings.symbols == ("EURUSD", "GBPUSD")
    assert settings.timeframes == ("D1", "H4")
    assert settings.execution.enabled is True
    assert settings.mt5.enabled is True
    assert settings.mt5.server == "Demo-Server"
    assert settings.mt5.login == 12345
    assert settings.mt5.password == "secret"
    assert settings.mt5.has_accounts is True
    assert settings.mt5.accounts[0].label == "primary"
    assert settings.mt5.accounts[1].label == "secondary"
    assert settings.monitoring.enabled is False
    assert settings.storage.logs == Path("demo-storage/logs")
