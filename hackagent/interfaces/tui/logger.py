# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
TUI Logging Handler and Decorator

This module provides a thread-safe logging system for displaying attack
execution logs in the TUI. It includes:
- A custom logging handler that captures logs for TUI display
- A decorator that can be applied to any attack's run() method
- Thread-safe log transmission to the TUI
"""

import logging
import threading
from collections import deque
from typing import Any, Callable, Deque, Optional, TypeVar

from textual.app import App

# Type variable for preserving function signatures
F = TypeVar("F", bound=Callable[..., Any])


class TUILogHandler(logging.Handler):
    """
    Thread-safe logging handler that captures logs for TUI display.

    This handler captures log records and transmits them to the TUI
    via a thread-safe callback mechanism. It supports:
    - Thread-safe log transmission
    - Log level filtering
    - Bounded buffer to prevent memory overflow
    - Graceful handling of TUI disconnection
    """

    def __init__(
        self,
        app: Optional[App] = None,
        callback: Optional[Callable[[str, str], None]] = None,
        max_buffer_size: int = 1000,
        level: int = logging.INFO,
    ):
        """
        Initialize the TUI log handler.

        Args:
            app: Textual App instance for thread-safe calls
            callback: Function to call with (message, level) for each log
            max_buffer_size: Maximum number of logs to buffer
            level: Minimum log level to capture (default: INFO)
        """
        super().__init__(level=level)
        self.app = app
        self.callback = callback
        self.max_buffer_size = max_buffer_size
        self.buffer: Deque[tuple[str, str]] = deque(maxlen=max_buffer_size)
        self._lock = threading.Lock()
        self._active = True

        # Set formatter for consistent log formatting
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%H:%M:%S",
        )
        self.setFormatter(formatter)

    def emit(self, record: logging.LogRecord) -> None:
        """
        Emit a log record to the TUI.

        This method is called by the logging system for each log entry.
        It formats the record and transmits it to the TUI via the callback.

        Args:
            record: The log record to emit
        """
        if not self._active:
            return

        try:
            # Format the log message
            log_entry = self.format(record)
            level_name = record.levelname

            # Store in buffer
            with self._lock:
                self.buffer.append((log_entry, level_name))

            # Transmit to TUI if callback is available
            if self.callback and self.app:
                try:
                    # Use app.call_from_thread for thread-safe TUI updates
                    self.app.call_from_thread(self.callback, log_entry, level_name)
                except Exception:
                    # If TUI callback fails, just continue (don't break logging)
                    # This could happen if the TUI is shutting down
                    pass

        except Exception:
            # Silently ignore errors in logging to prevent cascading failures
            self.handleError(record)

    def get_buffer(self) -> list[tuple[str, str]]:
        """
        Get all buffered log entries.

        Returns:
            List of (message, level) tuples
        """
        with self._lock:
            return list(self.buffer)

    def clear_buffer(self) -> None:
        """Clear all buffered log entries."""
        with self._lock:
            self.buffer.clear()

    def deactivate(self) -> None:
        """Deactivate the handler (stop emitting logs)."""
        self._active = False

    def activate(self) -> None:
        """Activate the handler (resume emitting logs)."""
        self._active = True
