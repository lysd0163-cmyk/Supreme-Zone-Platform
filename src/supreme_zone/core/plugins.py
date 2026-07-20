from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from .exceptions import PluginError


class Plugin(Protocol):
    name: str

    def activate(self) -> None: ...


@dataclass(slots=True)
class PluginRegistry:
    plugins: dict[str, Plugin] = field(default_factory=dict)

    def register(self, plugin: Plugin) -> None:
        if not getattr(plugin, "name", None):
            raise PluginError("Plugin must define a name")
        self.plugins[plugin.name] = plugin

    def activate_all(self) -> None:
        for plugin in self.plugins.values():
            plugin.activate()
