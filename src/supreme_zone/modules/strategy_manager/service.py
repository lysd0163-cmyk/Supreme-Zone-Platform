from __future__ import annotations

from pathlib import Path
from typing import Iterable

from .models import StrategyDefinition
from .registry import StrategyRegistry


class StrategyManager:
    def __init__(self, registry: StrategyRegistry | None = None) -> None:
        self.registry = registry or StrategyRegistry()

    def add_strategy_file(self, path: str | Path) -> StrategyDefinition:
        return self.registry.add_from_file(path)

    def activate_strategy(self, name: str) -> StrategyDefinition:
        return self.registry.set_active(name)

    def get_active_strategy(self) -> StrategyDefinition | None:
        return self.registry.active()

    def list_strategies(self) -> Iterable[StrategyDefinition]:
        return self.registry.strategies.values()
