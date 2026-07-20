from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Any

HealthCheck = Callable[[], bool]


@dataclass(slots=True)
class HealthMonitor:
    checks: dict[str, HealthCheck] = field(default_factory=dict)

    def register(self, name: str, check: HealthCheck) -> None:
        self.checks[name] = check

    def run(self) -> dict[str, bool]:
        return {name: check() for name, check in self.checks.items()}

    def is_healthy(self) -> bool:
        results = self.run()
        return all(results.values()) if results else True
