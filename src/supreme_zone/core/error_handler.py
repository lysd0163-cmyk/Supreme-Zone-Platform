from __future__ import annotations

import json
import logging
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from traceback import format_exception
from typing import Any


@dataclass(slots=True)
class ErrorRecord:
    timestamp: str
    context: str
    error_type: str
    message: str
    details: str


class ErrorHandler:
    def __init__(self, logger: logging.Logger, error_log_path: str | Path = "storage/logs/errors.jsonl") -> None:
        self.logger = logger
        self.error_log_path = Path(error_log_path)
        self.error_log_path.parent.mkdir(parents=True, exist_ok=True)

    def handle_exception(self, exc: BaseException, context: str = "runtime") -> ErrorRecord:
        record = ErrorRecord(
            timestamp=datetime.now(timezone.utc).isoformat(),
            context=context,
            error_type=type(exc).__name__,
            message=str(exc),
            details="".join(format_exception(type(exc), exc, exc.__traceback__)).strip(),
        )
        self._write(record)
        self.logger.error("%s: %s", record.error_type, record.message)
        self.logger.debug(record.details)
        return record

    def install_global_hook(self) -> None:
        def _hook(exc_type: type[BaseException], exc: BaseException, tb: Any) -> None:
            self.handle_exception(exc, context="uncaught-exception")

        sys.excepthook = _hook

    def _write(self, record: ErrorRecord) -> None:
        with self.error_log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")
