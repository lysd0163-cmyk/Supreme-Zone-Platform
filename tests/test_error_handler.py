from __future__ import annotations

import logging

from supreme_zone.core.error_handler import ErrorHandler


def test_error_handler_writes_jsonl(tmp_path) -> None:
    logger = logging.getLogger("error-handler-test")
    logger.handlers.clear()
    logger.addHandler(logging.NullHandler())

    handler = ErrorHandler(logger, tmp_path / "errors.jsonl")
    record = handler.handle_exception(ValueError("boom"), context="startup")

    assert record.error_type == "ValueError"
    assert record.context == "startup"
    assert record.message == "boom"
    contents = (tmp_path / "errors.jsonl").read_text(encoding="utf-8")
    assert "ValueError" in contents
    assert "boom" in contents
