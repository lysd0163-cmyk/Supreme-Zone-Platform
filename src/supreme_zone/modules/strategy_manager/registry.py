from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ...core.exceptions import StrategyError
from .loader import StrategyLoader
from .models import StrategyDefinition


@dataclass(slots=True)
class StrategyRegistry:
    strategies: dict[str, StrategyDefinition] = field(default_factory=dict)
    active_strategy_name: str | None = None

    def add_from_file(self, path: str | Path) -> StrategyDefinition:
        strategy = StrategyLoader().load(path)
        self.strategies[strategy.name] = strategy
        if strategy.active:
            self.active_strategy_name = strategy.name
        return strategy

    def set_active(self, name: str) -> StrategyDefinition:
        try:
            strategy = self.strategies[name]
        except KeyError as exc:
            raise StrategyError(f"Unknown strategy: {name}") from exc
        self.active_strategy_name = name
        strategy.active = True
        return strategy

    def active(self) -> StrategyDefinition | None:
        if self.active_strategy_name is None:
            return None
        return self.strategies.get(self.active_strategy_name)
