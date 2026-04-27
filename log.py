"""Centralized logging configuration for OnyxKraken."""

import logging
import sys


def get_logger(name: str) -> logging.Logger:
    """Get a named logger with consistent formatting."""
    return logging.getLogger(f"onyx.{name}")


def setup_logging(level: str = "INFO"):
    """Configure the root onyx logger with console output.

    Args:
        level: One of DEBUG, INFO, WARNING, ERROR.
    """
    root = logging.getLogger("onyx")
    if root.handlers:
        return  # already configured

    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(
        "%(message)s"
    ))
    root.addHandler(handler)
