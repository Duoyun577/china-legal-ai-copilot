"""应用错误日志初始化。"""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from types import TracebackType

from config.settings import PROJECT_ROOT


LOGGER_NAME = "china_legal_ai"


def initialize_logging(log_path: str | Path | None = None) -> logging.Logger:
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    target = Path(log_path or PROJECT_ROOT / "logs" / "app.log").resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    if not any(isinstance(handler, RotatingFileHandler) and Path(handler.baseFilename) == target for handler in logger.handlers):
        handler = RotatingFileHandler(target, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
        logger.addHandler(handler)
    sys.excepthook = _uncaught_exception_hook
    logger.info("application_logging_initialized")
    return logger


def get_logger() -> logging.Logger:
    logger = logging.getLogger(LOGGER_NAME)
    return logger if logger.handlers else initialize_logging()


def log_exception(context: str, exc: BaseException) -> None:
    get_logger().error(context, exc_info=(type(exc), exc, exc.__traceback__))


def _uncaught_exception_hook(exc_type: type[BaseException], exc: BaseException, traceback: TracebackType | None) -> None:
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc, traceback)
        return
    get_logger().critical("uncaught_exception", exc_info=(exc_type, exc, traceback))
