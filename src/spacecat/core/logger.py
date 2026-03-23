"""This module sets up the global logging configuration."""

import logging
import sys
from logging.handlers import RotatingFileHandler


def setup_logging() -> None:
    """Sets up the global logging configuration."""
    log_formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )

    # 1. Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(log_formatter)

    # 2. File Handler
    file_handler = RotatingFileHandler("spacecat.log", maxBytes=5 * 1024 * 1024, backupCount=5)
    file_handler.setFormatter(log_formatter)

    # 3. Root Logger Configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    # Silence noisy 3rd party libs if needed
    logging.getLogger("tortoise").setLevel(logging.WARNING)
