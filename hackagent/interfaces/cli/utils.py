# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
CLI Utilities

Common utilities for the HackAgent CLI including error handling,
formatting, and helper functions.
"""

import functools
import json
from pathlib import Path
from typing import Any, Dict

import click
from rich.markup import escape
from rich.traceback import Traceback

from hackagent import ApiError, HackAgentError
from hackagent.core.settings import tls_error_hint
from hackagent.interfaces.palette import console as themed

console = themed()
#: Where warnings and failures go, so that ``--json`` output on stdout stays
#: parseable whatever happens.
errors = themed(stderr=True)


class Failed(click.ClickException):
    """A command that failed, said as every failure is: ``✗ what went
    wrong``, in the palette's colour, rather than Click's ``Error:``."""

    def show(self, file=None) -> None:  # noqa: D102 - Click's own hook
        themed(stderr=True).print(
            f"[failed]✗[/failed] {escape(self.format_message())}", soft_wrap=True
        )


def handle_errors(func):
    """Decorator for consistent error handling across CLI commands"""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except (click.ClickException, click.exceptions.Exit, click.Abort):
            # Raised deliberately, and Click already renders it. Catching it
            # below would report the same failure a second time, as an
            # "unexpected" one.
            raise
        # ApiError is a HackAgentError, so it is caught first.
        except ApiError as e:
            _traceback_when_debugging()
            raise Failed(f"API error: {e}") from e
        except (HackAgentError, ValueError, FileNotFoundError) as e:
            _traceback_when_debugging()
            raise Failed(str(e)) from e
        except Exception as e:
            hint = tls_error_hint(e)
            if hint:
                raise Failed(f"TLS certificate error: {e}\n{hint}") from e
            _traceback_when_debugging()
            raise Failed(f"Unexpected error: {e}") from e

    return wrapper


def _traceback_when_debugging() -> None:
    if console._environ.get("HACKAGENT_DEBUG"):
        errors.print(Traceback())


def load_config_file(path: str) -> Dict[str, Any]:
    """Load configuration from YAML or JSON file"""
    config_path = Path(path)

    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {path}")

    try:
        with open(config_path) as f:
            if config_path.suffix.lower() in [".yaml", ".yml"]:
                try:
                    import yaml

                    return yaml.safe_load(f) or {}
                except ImportError:
                    raise Failed(
                        "PyYAML required for YAML config files. Install with: pip install pyyaml"
                    )
            else:
                return json.load(f)
    except json.JSONDecodeError as e:
        raise Failed(f"Invalid JSON in config file {path}: {e}")
    except Exception as e:
        raise Failed(f"Failed to load config file {path}: {e}")


def display_success(message: str) -> None:
    """``✓ message``: something done, or a check passed."""
    console.print(f"[passed]✓[/passed] {message}")


def display_warning(message: str) -> None:
    """``! message``: worth knowing, not a failure. Written to stderr."""
    errors.print(f"[warning]![/warning] {message}")


def display_error(message: str) -> None:
    """``✗ message``: something that failed. Written to stderr."""
    errors.print(f"[failed]✗[/failed] {message}")


def display_info(message: str) -> None:
    """A message in passing."""
    console.print(f"[secondary]{message}[/secondary]")


def display_heading(title: str) -> None:
    """A section's title, with a blank line above it."""
    console.print(f"\n[heading]{title}[/heading]")


def display_hint(what: str, command: str) -> None:
    """What to do next, and the command that does it."""
    console.print(f"  [secondary]{what}:[/secondary] [accent]{command}[/accent]")
