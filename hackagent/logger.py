# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0


import logging
import os

from rich.logging import RichHandler

_rich_handler_configured_for_package = False


def setup_package_logging(
    logger_name: str = "hackagent", default_level_str: str = "WARNING"
):
    """Configures RichHandler for the specified logger if not already set."""
    global _rich_handler_configured_for_package

    package_logger = logging.getLogger(logger_name)

    if logger_name == "hackagent" and _rich_handler_configured_for_package:
        return

    has_console_handler = any(
        isinstance(h, logging.StreamHandler) for h in package_logger.handlers
    )

    if not has_console_handler:
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
            # Set default levels for common noisy libraries
            logging.getLogger("httpx").setLevel(logging.WARNING)
            logging.getLogger("litellm").setLevel(logging.WARNING)
            # Add other libraries here if needed, e.g.:
            # logging.getLogger("another_library").setLevel(logging.WARNING)

        # package_logger.debug(f"RichHandler configured for '{logger_name}' logger at level {level}.")

    elif any(isinstance(h, RichHandler) for h in package_logger.handlers):
        if logger_name == "hackagent":
            _rich_handler_configured_for_package = True

    return package_logger


def get_logger(name: str) -> logging.Logger:
    """
    Retrieves a logger instance.
    If the logger is 'hackagent' or starts with 'hackagent.',
    it ensures the package logging is set up.
    """
    if name == "hackagent" or name.startswith("hackagent."):
        # Ensure base "hackagent" logger is configured first
        setup_package_logging(logger_name="hackagent")
    return logging.getLogger(name)
