from __future__ import annotations

from pathlib import Path
from typing import Any

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

    def validate_interpreted_payload(self, payload: dict[str, Any]) -> None:
        # Keep validation permissive so strategy upload cannot fail on strict parsing rules.
        self.validate_payload(payload)
        interpreter = payload.get("interpreter")
        if not isinstance(interpreter, dict):
            raise StrategyError("Strategy payload must include an interpreter model")

        title = str(interpreter.get("title", payload.get("name", ""))).upper()
        if "SUPREME ZONE ENGINE" not in title:
            raise StrategyError("Only SUPREME ZONE ENGINE strategies are allowed")

        # Everything else is advisory for now; the interpreter already extracted the
        # document into a strategy model and the upload endpoint should not fail on
        # missing optional terms while Render is being stabilized.
        return
