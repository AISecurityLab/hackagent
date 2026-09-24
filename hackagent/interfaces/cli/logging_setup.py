# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0


"""Rich console logging for the CLI and TUI.

The library never installs handlers; the command-line entry point calls
:func:`setup_package_logging` once at startup.
"""

import logging
import os

from rich.logging import RichHandler

_rich_handler_configured_for_package = False


def setup_package_logging(
    logger_name: str = "hackagent", default_level_str: str = "WARNING"
) -> logging.Logger:
    """Configures RichHandler for the specified logger if not already set."""
    global _rich_handler_configured_for_package

    package_logger = logging.getLogger(logger_name)

    if logger_name == "hackagent" and _rich_handler_configured_for_package:
        return package_logger

    # Use RichHandler specifically — StreamHandler is too broad since
    # RichHandler is a subclass and would incorrectly match the guard.
    has_rich_handler = any(isinstance(h, RichHandler) for h in package_logger.handlers)

    if not has_rich_handler:
        log_level_env = os.getenv(
            f"{logger_name.upper()}_LOG_LEVEL", default_level_str
        ).upper()
        level = getattr(logging, log_level_env, logging.WARNING)
        package_logger.setLevel(level)

        rich_handler = RichHandler(
            show_time=True,
            show_level=True,
            show_path=False,
            markup=True,
            rich_tracebacks=True,
            tracebacks_show_locals=False,
        )
        package_logger.addHandler(rich_handler)
        package_logger.propagate = False  # Avoid duplicate logs with root logger

    if logger_name == "hackagent":
        _rich_handler_configured_for_package = True

    return package_logger


def suppress_noisy_libraries(*names: str) -> None:
    """
    Silence chatty third-party loggers to WARNING.

    This is opt-in so that applications embedding hackagent are not surprised
    by their own library loggers being muted.

    Example:
        >>> from hackagent.interfaces.cli.logging_setup import suppress_noisy_libraries
        >>> suppress_noisy_libraries("httpx", "litellm", "urllib3")
    """
    for name in names:
        logging.getLogger(name).setLevel(logging.WARNING)
