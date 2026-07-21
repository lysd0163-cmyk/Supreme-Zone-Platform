from __future__ import annotations

from dataclasses import dataclass, field
from threading import Event, Thread
from time import sleep
from typing import Callable, Any


Job = Callable[[], Any]


@dataclass(slots=True)
class UpdateScheduler:
    interval_seconds: int = 60
    _jobs: dict[str, Job] = field(default_factory=dict)
    _thread: Thread | None = field(default=None, init=False)
    _stop_event: Event = field(default_factory=Event, init=False)

    def register(self, name: str, job: Job) -> None:
        self._jobs[name] = job

    def unregister(self, name: str) -> None:
        self._jobs.pop(name, None)

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)

    def _run(self) -> None:
        while not self._stop_event.is_set():
            for job in list(self._jobs.values()):
                job()
            sleep(max(self.interval_seconds, 1))
