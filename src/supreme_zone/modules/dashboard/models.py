from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True, frozen=True)
class DashboardSnapshot:
    title: str
    sections: dict[str, Any] = field(default_factory=dict)
    generated_at: str = ""


@dataclass(slots=True, frozen=True)
class DashboardArtifact:
    html_path: Path
    json_path: Path | None = None
