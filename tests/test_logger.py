"""core/logger.py 테스트."""

import logging
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.logger import setup_logger, LOG_DIR


def test_setup_logger_creates_log_dir():
    logger = setup_logger("test-logger")
    assert LOG_DIR.exists()
    assert isinstance(logger, logging.Logger)
    assert logger.name == "test-logger"


def test_setup_logger_has_handlers():
    name = "test-logger-handlers"
    logger = setup_logger(name)
    assert len(logger.handlers) >= 2  # file + stream


def test_setup_logger_idempotent():
    name = "test-logger-idempotent"
    logger1 = setup_logger(name)
    handler_count = len(logger1.handlers)
    logger2 = setup_logger(name)
    assert logger1 is logger2
    assert len(logger2.handlers) == handler_count
