from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from .exceptions import ServiceResolutionError

Provider = Callable[["ServiceContainer"], Any]


@dataclass(slots=True)
class ServiceContainer:
    _instances: dict[Any, Any] = field(default_factory=dict)
    _factories: dict[Any, Provider] = field(default_factory=dict)
    _resolving: set[Any] = field(default_factory=set)

    def register_instance(self, key: Any, instance: Any) -> None:
        self._instances[key] = instance

    def register_factory(self, key: Any, factory: Provider) -> None:
        self._factories[key] = factory

    def has(self, key: Any) -> bool:
        return key in self._instances or key in self._factories

    def resolve(self, key: Any) -> Any:
        if key in self._instances:
            return self._instances[key]
        if key not in self._factories:
            raise ServiceResolutionError(f"Service not registered: {key!r}")
        if key in self._resolving:
            raise ServiceResolutionError(f"Circular service resolution detected: {key!r}")

        self._resolving.add(key)
        try:
            value = self._factories[key](self)
            self._instances[key] = value
            return value
        finally:
            self._resolving.discard(key)
