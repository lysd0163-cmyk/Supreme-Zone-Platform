from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class BootstrapResult:
    ready: bool
    app_name: str
    config_path: Path
    storage_root: Path
    services_registered: tuple[str, ...] = field(default_factory=tuple)
    platform: Any | None = None
