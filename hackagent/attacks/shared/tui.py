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
Shared TUI logging decorator.

Provides a single, lazy-loaded TUI logging decorator used by all attack
techniques. This eliminates the ~20-line copy-pasted boilerplate in each
technique's attack.py.

Usage:
    from hackagent.attacks.shared.tui import with_tui_logging

    class MyAttack(BaseAttack):
        @with_tui_logging(logger_name="hackagent.attacks", level=logging.INFO)
        def run(self, goals):
            ...
"""

# Lazy-loaded singleton
_with_tui_logging = None


def _get_tui_logging_decorator():
    """Lazily import the TUI logging decorator to avoid circular imports."""
    global _with_tui_logging
    if _with_tui_logging is not None:
        return _with_tui_logging

    try:
        from hackagent.cli.tui.logger import with_tui_logging as _real

        _with_tui_logging = _real
    except ImportError:
        # Fallback: no-op decorator if TUI module is not installed
        def _noop(*args, **kwargs):
            def decorator(func):
                return func

            return decorator

        _with_tui_logging = _noop

    return _with_tui_logging


def with_tui_logging(*args, **kwargs):
    """
    TUI-aware logging decorator (lazy-loaded).

    Wraps the real TUI logging decorator from hackagent.cli.tui.logger,
    falling back to a no-op if the TUI module is not available.

    Args:
        *args, **kwargs: Passed through to the real decorator.

    Returns:
        Decorated function with TUI logging support.
    """
    decorator = _get_tui_logging_decorator()
    return decorator(*args, **kwargs)
