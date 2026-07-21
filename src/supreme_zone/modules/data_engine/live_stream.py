from __future__ import annotations

from dataclasses import dataclass, field
from threading import Event, Thread
from time import sleep
from typing import Callable, Any

from ...core.error_handler import ErrorHandler
from .errors import DataSyncError
from .service import DataEngine


@dataclass(slots=True)
class LiveStreamStatus:
    running: bool = False
    cycles_completed: int = 0
    last_error: str | None = None


@dataclass(slots=True)
class LiveDataStream:
    engine: DataEngine
    interval_seconds: int = 60
    error_handler: ErrorHandler | None = None
    on_cycle_complete: Callable[[dict[str, Any]], None] | None = None
    _stop_event: Event = field(default_factory=Event, init=False)
    _thread: Thread | None = field(default=None, init=False)
    status: LiveStreamStatus = field(default_factory=LiveStreamStatus, init=False)

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self.status.running = True
        self._thread = Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        self.status.running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)

    def run_once(self) -> list[dict[str, Any]]:
        if not self.engine.status.mt5_connected:
            self.engine.connect_mt5()
        results = self.engine.sync_all()
        self.status.cycles_completed += 1
        if self.on_cycle_complete is not None:
            for result in results:
                self.on_cycle_complete(result)
        return results

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.run_once()
                self.status.last_error = None
            except Exception as exc:  # pragma: no cover - defensive runtime loop
                self.status.last_error = str(exc)
                if self.error_handler is not None:
                    self.error_handler.handle_exception(exc, context="live-stream")
                if not self.engine.status.mt5_connected:
                    try:
                        self.engine.connect_mt5()
                    except Exception as reconnect_exc:
                        self.status.last_error = str(reconnect_exc)
                        if self.error_handler is not None:
                            self.error_handler.handle_exception(reconnect_exc, context="live-reconnect")
            sleep(max(self.interval_seconds, 1))
