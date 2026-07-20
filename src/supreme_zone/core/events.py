from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from .exceptions import EventBusError

Handler = Callable[[Any], Any]


@dataclass(slots=True)
class EventBus:
    _handlers: dict[str, list[Handler]] = field(default_factory=dict)

    def subscribe(self, event_name: str, handler: Handler) -> None:
        handlers = self._handlers.setdefault(event_name, [])
        handlers.append(handler)

    def publish(self, event_name: str, payload: Any = None) -> list[Any]:
        handlers = self._handlers.get(event_name, [])
        if not handlers:
            return []
        results: list[Any] = []
        for handler in handlers:
            try:
                results.append(handler(payload))
            except Exception as exc:  # pragma: no cover - defensive
                raise EventBusError(f"Event handler failed for {event_name!r}") from exc
        return results

    def clear(self, event_name: str | None = None) -> None:
        if event_name is None:
            self._handlers.clear()
            return
        self._handlers.pop(event_name, None)
