from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ...core.exceptions import StrategyError
from .loader import StrategyLoader
from .models import StrategyDefinition


@dataclass(slots=True)
class StrategyRegistry:
    strategies: dict[str, StrategyDefinition] = field(default_factory=dict)
    versions: dict[str, list[StrategyDefinition]] = field(default_factory=dict)
    active_strategy_name: str | None = None

    def add_from_file(self, path: str | Path) -> StrategyDefinition:
        strategy = StrategyLoader().load(path)
        self.strategies[strategy.name] = strategy
        self.versions.setdefault(strategy.name, []).append(strategy)
        self._activate(strategy.name)
        return strategy

    def set_active(self, name: str) -> StrategyDefinition:
        try:
            strategy = self.strategies[name]
        except KeyError as exc:
            raise StrategyError(f"Unknown strategy: {name}") from exc
        self._activate(name)
        return strategy

    def _activate(self, name: str) -> None:
        for item in self.strategies.values():
            item.active = False
        self.active_strategy_name = name
        if name in self.strategies:
            self.strategies[name].active = True

    def clear_active(self) -> None:
        self.active_strategy_name = None
        for strategy in self.strategies.values():
            strategy.active = False

    def active(self) -> StrategyDefinition | None:
        if self.active_strategy_name is None:
            return None
        return self.strategies.get(self.active_strategy_name)

    def history(self, name: str | None = None) -> dict[str, list[StrategyDefinition]] | list[StrategyDefinition]:
        if name is not None:
            return list(self.versions.get(name, []))
        return {strategy_name: list(items) for strategy_name, items in self.versions.items()}
