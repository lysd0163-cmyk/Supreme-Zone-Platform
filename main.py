from supreme_zone.core.bootstrap import bootstrap
from supreme_zone.core.error_handler import ErrorHandler
from supreme_zone.core.logger import configure_logging


if __name__ == "__main__":
    try:
        result = bootstrap()
        print(f"{result.app_name} ready: {result.ready}")
    except Exception as exc:  # pragma: no cover - startup safety
        logger = configure_logging()
        handler = ErrorHandler(logger)
        handler.handle_exception(exc, context="startup")
        raise
