from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from supreme_zone.core import cli
from supreme_zone.modules.analysis_engine.models import ZoneCandidate, ZoneSide
from supreme_zone.modules.data_engine.market import MarketBar
from supreme_zone.modules.validation_engine.service import ValidationEngine


@dataclass
class _FakePlatform:
    once_called: bool = False
    forever_called: bool = False
    last_kwargs: dict | None = None

    def run_once(self, **kwargs):
        self.once_called = True
        self.last_kwargs = kwargs
        return None

    def run_forever(self, **kwargs):
        self.forever_called = True
        self.last_kwargs = kwargs
        raise RuntimeError("stop-test")


@dataclass
class _FakeBootstrapResult:
    platform: _FakePlatform


def test_cli_runs_once_mode(monkeypatch) -> None:
    platform = _FakePlatform()
    monkeypatch.setattr(cli, "bootstrap", lambda: _FakeBootstrapResult(platform=platform))

    exit_code = cli.main(["--symbols", "EURUSD,GBPUSD", "--bars", "50"])

    assert exit_code == 0
    assert platform.once_called is True
    assert platform.last_kwargs["symbols"] == ("EURUSD", "GBPUSD")
    assert platform.last_kwargs["bars"] == 50


def test_cli_runs_live_mode(monkeypatch) -> None:
    platform = _FakePlatform()
    monkeypatch.setattr(cli, "bootstrap", lambda: _FakeBootstrapResult(platform=platform))

    try:
        cli.main(["--live", "--interval", "1"])
    except RuntimeError as exc:
        assert str(exc) == "stop-test"

    assert platform.forever_called is True
    assert platform.last_kwargs["interval_seconds"] == 1


def test_validation_engine_uses_governance_audit() -> None:
    engine = ValidationEngine()
    candidate = ZoneCandidate(ZoneSide.BUY, "M15", "EURUSD", 1.0, 1.1, 90.0, "test")
    bars = [MarketBar(time=__import__("datetime").datetime(2026, 1, 1), open=1.0, high=1.12, low=0.98, close=1.05)]
    audit = {
        "passed": True,
        "score": 18,
        "required": 18,
        "passed_layers": tuple(),
        "failed_layers": tuple(),
    }

    result = engine.validate_candidate(candidate, bars, audit=audit)

    assert result.is_valid is True
    assert result.metadata["governance"]["passed"] is True
    assert result.status.value in {"FRESH", "MITIGATED"}
