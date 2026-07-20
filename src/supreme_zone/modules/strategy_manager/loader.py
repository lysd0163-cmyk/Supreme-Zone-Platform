from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from .models import StrategyDefinition
from .validator import StrategyValidator


class StrategyLoader:
    def __init__(self) -> None:
        self.validator = StrategyValidator()

    def load(self, path: str | Path) -> StrategyDefinition:
        strategy_path = Path(path)
        self.validator.validate_path(strategy_path)

        suffix = strategy_path.suffix.lower()
        if suffix in {".yaml", ".yml"}:
            payload: Any = yaml.safe_load(strategy_path.read_text(encoding="utf-8"))
        elif suffix == ".json":
            payload = json.loads(strategy_path.read_text(encoding="utf-8"))
        else:
            payload = {"name": strategy_path.stem, "version": "1.0.0", "source": strategy_path.read_text(encoding="utf-8")}

        self.validator.validate_payload(payload)
        return StrategyDefinition(
            name=str(payload.get("name")),
            version=str(payload.get("version", "1.0.0")),
            source_path=strategy_path,
            raw=payload,
            active=bool(payload.get("active", False)),
        )
