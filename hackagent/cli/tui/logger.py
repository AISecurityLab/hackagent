# Copyright 2025 - AI4I. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
TUI Logging Handler and Decorator

This module provides a thread-safe logging system for displaying attack
execution logs in the TUI. It includes:
- A custom logging handler that captures logs for TUI display
- A decorator that can be applied to any attack's run() method
- Thread-safe log transmission to the TUI
"""

import functools
import logging
import threading
from collections import deque
from typing import Any, Callable, Deque, Optional, TypeVar, cast

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


def with_tui_logging(
    logger_name: str = "hackagent",
    level: int = logging.INFO,
) -> Callable[[F], F]:
    """
    Decorator that captures logs from an attack's run() method for TUI display.

    This decorator can be applied to any attack class's run() method to
    automatically capture and display logs in the TUI. It:
    - Temporarily attaches a TUI log handler
    - Captures logs during attack execution
    - Removes the handler after completion
    - Works with both sync and async methods
    - Preserves the original return value

    Usage:
        class MyAttack(BaseAttack):
            @with_tui_logging(logger_name="hackagent.attacks.myattack")
            def run(self, goals: List[str]) -> pd.DataFrame:
                # Attack logic here
                return results

    Args:
        logger_name: Name of the logger to attach the handler to
        level: Minimum log level to capture (default: INFO)

    Returns:
        Decorator function that wraps the attack's run method
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(self, *args: Any, **kwargs: Any) -> Any:
            # Get the logger to attach the handler to
            target_logger = logging.getLogger(logger_name)

            # Try to get TUI log handler from the attack instance
            tui_handler: Optional[TUILogHandler] = None
            if hasattr(self, "_tui_log_handler"):
                tui_handler = self._tui_log_handler

            # If we have a TUI handler, attach it to the logger
            if tui_handler:
                tui_handler.activate()
                target_logger.addHandler(tui_handler)
                target_logger.setLevel(level)

                # Attach to ALL child loggers under this logger hierarchy
                # This ensures logs from submodules (e.g., AdvPrefix/*) are captured
                for existing_logger_name in list(
                    logging.Logger.manager.loggerDict.keys()
                ):
                    if existing_logger_name.startswith(logger_name + "."):
                        child_logger = logging.getLogger(existing_logger_name)
                        if tui_handler not in child_logger.handlers:
                            child_logger.addHandler(tui_handler)
                            child_logger.setLevel(level)

                # Also attach to router loggers to capture agent interactions
                router_logger = logging.getLogger("hackagent.router")
                if tui_handler not in router_logger.handlers:
                    router_logger.addHandler(tui_handler)
                    router_logger.setLevel(level)

                # Attach to router child loggers (adapters)
                for existing_logger_name in list(
                    logging.Logger.manager.loggerDict.keys()
                ):
                    if existing_logger_name.startswith("hackagent.router."):
                        child_logger = logging.getLogger(existing_logger_name)
                        if tui_handler not in child_logger.handlers:
                            child_logger.addHandler(tui_handler)
                            child_logger.setLevel(level)

                # Also attach to the attack module logger for backward compatibility
                attack_module_logger = logging.getLogger(self.__class__.__module__)
                if tui_handler not in attack_module_logger.handlers:
                    attack_module_logger.addHandler(tui_handler)
                    attack_module_logger.setLevel(level)

            try:
                # Execute the actual attack run method
                result = func(self, *args, **kwargs)
                return result

            finally:
                # Always remove the handler when done
                if tui_handler:
                    tui_handler.deactivate()
                    # Remove from base logger
                    if tui_handler in target_logger.handlers:
                        target_logger.removeHandler(tui_handler)

                    # Remove from all child loggers under attack hierarchy
                    for existing_logger_name in list(
                        logging.Logger.manager.loggerDict.keys()
                    ):
                        if existing_logger_name.startswith(logger_name + "."):
                            child_logger = logging.getLogger(existing_logger_name)
                            if tui_handler in child_logger.handlers:
                                child_logger.removeHandler(tui_handler)

                    # Remove from router loggers
                    router_logger = logging.getLogger("hackagent.router")
                    if tui_handler in router_logger.handlers:
                        router_logger.removeHandler(tui_handler)

                    for existing_logger_name in list(
                        logging.Logger.manager.loggerDict.keys()
                    ):
                        if existing_logger_name.startswith("hackagent.router."):
                            child_logger = logging.getLogger(existing_logger_name)
                            if tui_handler in child_logger.handlers:
                                child_logger.removeHandler(tui_handler)

                    # Remove from attack module logger
                    if self.__class__.__module__:
                        attack_module_logger = logging.getLogger(
                            self.__class__.__module__
                        )
                        if tui_handler in attack_module_logger.handlers:
                            attack_module_logger.removeHandler(tui_handler)

        return cast(F, wrapper)

    return decorator


def attach_tui_handler(
    attack_instance: Any,
    app: App,
    callback: Callable[[str, str], None],
    max_buffer_size: int = 1000,
    level: int = logging.INFO,
) -> TUILogHandler:
    """
    Attach a TUI log handler to an attack instance.

    This function should be called before executing an attack to set up
    the logging infrastructure for TUI display.

    Args:
        attack_instance: The attack object to attach the handler to
        app: Textual App instance for thread-safe calls
        callback: Function to call with (message, level) for each log
        max_buffer_size: Maximum number of logs to buffer
        level: Minimum log level to capture

    Returns:
        The created TUILogHandler instance
    """
    handler = TUILogHandler(
        app=app,
        callback=callback,
        max_buffer_size=max_buffer_size,
        level=level,
    )

    # Store the handler on the attack instance
    attack_instance._tui_log_handler = handler

    return handler


def detach_tui_handler(attack_instance: Any) -> Optional[TUILogHandler]:
    """
    Detach and return the TUI log handler from an attack instance.

    Args:
        attack_instance: The attack object to detach the handler from

    Returns:
        The detached TUILogHandler instance, or None if not present
    """
    if hasattr(attack_instance, "_tui_log_handler"):
        handler = attack_instance._tui_log_handler
        delattr(attack_instance, "_tui_log_handler")
        return handler
    return None
