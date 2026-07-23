from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from pypdf import PdfReader

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
        elif suffix == ".pdf":
            payload = self._pdf_payload(strategy_path)
        else:
            payload = {
                "name": strategy_path.stem,
                "version": "1.0.0",
                "source": strategy_path.read_text(encoding="utf-8"),
            }

        if isinstance(payload, dict) and payload.get("name"):
            self.validator.validate_payload(payload)
            name = str(payload.get("name"))
            version = str(payload.get("version", "1.0.0"))
            active = bool(payload.get("active", False))
        else:
            name = strategy_path.stem
            version = "1.0.0"
            active = False
            payload = {
                "name": name,
                "version": version,
                "source": payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False),
                "active": active,
            }

        return StrategyDefinition(
            name=name,
            version=version,
            source_path=strategy_path,
            raw=payload if isinstance(payload, dict) else {"source": payload},
            active=active,
        )

    def _pdf_payload(self, path: Path) -> dict[str, Any]:
        reader = PdfReader(str(path))
        pages = [page.extract_text() or "" for page in reader.pages]
        text = "\n".join(pages).strip()
        return {
            "name": path.stem,
            "version": "1.0.0",
            "source": text,
            "format": "pdf",
        }
