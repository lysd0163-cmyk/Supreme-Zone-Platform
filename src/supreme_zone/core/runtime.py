from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class BootstrapResult:
    ready: bool
    app_name: str
    config_path: Path
    storage_root: Path
