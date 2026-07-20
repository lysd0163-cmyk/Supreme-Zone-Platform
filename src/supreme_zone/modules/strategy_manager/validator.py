from __future__ import annotations

from pathlib import Path

from ...core.exceptions import StrategyError


class StrategyValidator:
    def validate_path(self, path: Path) -> None:
        if not path.exists():
            raise StrategyError(f"Strategy file does not exist: {path}")
        if not path.is_file():
            raise StrategyError(f"Strategy path is not a file: {path}")

    def validate_payload(self, payload: object) -> None:
        if not isinstance(payload, dict):
            raise StrategyError("Strategy payload must be a mapping")
        if "name" not in payload:
            raise StrategyError("Strategy payload must contain a name")
