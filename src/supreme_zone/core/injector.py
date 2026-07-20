from __future__ import annotations

from inspect import Parameter, signature
from typing import Any, get_type_hints

from .container import ServiceContainer
from .exceptions import DependencyInjectionError


class DependencyInjector:
    def __init__(self, container: ServiceContainer) -> None:
        self.container = container

    def create(self, cls: type[Any]) -> Any:
        init = cls.__init__
        sig = signature(init)
        hints = get_type_hints(init)
        kwargs: dict[str, Any] = {}

        for name, param in sig.parameters.items():
            if name == "self" or param.kind in {Parameter.VAR_POSITIONAL, Parameter.VAR_KEYWORD}:
                continue

            annotation = hints.get(name, param.annotation)
            if annotation is Parameter.empty:
                if param.default is not Parameter.empty:
                    continue
                raise DependencyInjectionError(f"Missing annotation for dependency: {cls.__name__}.{name}")

            if self.container.has(annotation):
                kwargs[name] = self.container.resolve(annotation)
            elif param.default is not Parameter.empty:
                continue
            else:
                raise DependencyInjectionError(
                    f"Unresolved dependency for {cls.__name__}.{name}: {annotation!r}"
                )

        return cls(**kwargs)
