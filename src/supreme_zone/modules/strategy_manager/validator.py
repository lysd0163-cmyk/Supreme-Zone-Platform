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
        self.validate_payload(payload)
        interpreter = payload.get("interpreter")
        if not isinstance(interpreter, dict):
            raise StrategyError("Strategy payload must include an interpreter model")

        title = str(interpreter.get("title", payload.get("name", ""))).upper()
        if "SUPREME ZONE ENGINE" not in title:
            raise StrategyError("Only SUPREME ZONE ENGINE strategies are allowed")

        outputs = {str(item).upper().strip() for item in interpreter.get("official_outputs", ()) if str(item).strip()}
        buy_ok = any(label in outputs for label in ("BUY ZONE", "ZONE BUY", "OFFICIAL BUY ZONE"))
        sell_ok = any(label in outputs for label in ("SELL ZONE", "ZONE SELL", "OFFICIAL SELL ZONE"))
        if not (buy_ok and sell_ok):
            raise StrategyError("Strategy must define BUY ZONE and SELL ZONE")

        timeframes = {str(item).upper().strip() for item in interpreter.get("timeframes", ()) if str(item).strip()}
        required_timeframes = {"D1", "H4", "H1", "M15"}
        if not required_timeframes.issubset(timeframes):
            raise StrategyError("Strategy must include D1, H4, H1 and M15 in the hierarchy")

        core_terms = {str(item).upper().strip() for item in interpreter.get("core_terms", ()) if str(item).strip()}
        required_terms = {"ORIGIN", "DISPLACEMENT", "ORDER BLOCK", "FVG", "PREMIUM", "DISCOUNT", "BOS", "CHOCH"}
        if len(required_terms.intersection(core_terms)) < 4:
            raise StrategyError("Strategy interpretation is missing core Supreme Zone terms")

        if not bool(interpreter.get("is_supreme_zone_engine", False)):
            raise StrategyError("Strategy interpreter did not recognize the file as SUPREME ZONE ENGINE")
