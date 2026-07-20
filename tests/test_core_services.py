from __future__ import annotations

from dataclasses import dataclass

from supreme_zone.core.container import ServiceContainer
from supreme_zone.core.events import EventBus
from supreme_zone.core.health import HealthMonitor
from supreme_zone.core.injector import DependencyInjector


def test_service_container_registers_instances_and_factories() -> None:
    container = ServiceContainer()
    container.register_instance(int, 7)
    container.register_factory(str, lambda _: "ready")

    assert container.resolve(int) == 7
    assert container.resolve(str) == "ready"


@dataclass
class _Dependency:
    value: str


class _Consumer:
    def __init__(self, dependency: _Dependency) -> None:
        self.dependency = dependency


def test_dependency_injector_creates_objects() -> None:
    container = ServiceContainer()
    container.register_instance(_Dependency, _Dependency("wired"))

    injector = DependencyInjector(container)
    consumer = injector.create(_Consumer)

    assert consumer.dependency.value == "wired"


def test_event_bus_publishes_events() -> None:
    bus = EventBus()
    seen: list[dict[str, str]] = []

    bus.subscribe("system.ready", lambda payload: seen.append(payload))
    result = bus.publish("system.ready", {"state": "ok"})

    assert seen == [{"state": "ok"}]
    assert result == [None]


def test_health_monitor_runs_checks() -> None:
    monitor = HealthMonitor()
    monitor.register("config", lambda: True)
    monitor.register("storage", lambda: True)

    assert monitor.is_healthy() is True
    assert monitor.run() == {"config": True, "storage": True}
