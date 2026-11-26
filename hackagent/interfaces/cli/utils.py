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
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.traceback import Traceback

from hackagent import ApiError, HackAgentError
from hackagent.core.settings import tls_error_hint
from hackagent.interfaces.palette import console as themed

console = themed()


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
        console.print(Traceback())


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


def display_results_table(results: Any, title: str = "Results") -> None:
    """Display results in a formatted table"""
    if isinstance(results, list):
        if not results:
            console.print(f"[secondary]No {title.lower()} found[/secondary]")
            return

        # Try to create table from list of dicts
        if results and isinstance(results[0], dict):
            table = Table(title=title, show_header=True, header_style="heading")

            # Get all unique keys for columns
            all_keys = set()
            for item in results:
                all_keys.update(item.keys())

            # Add columns
            for key in sorted(all_keys):
                table.add_column(str(key))

            # Add rows (limit to first 20)
            for item in results[:20]:
                row_values = []
                for key in sorted(all_keys):
                    value = item.get(key, "")
                    row_values.append(str(value))
                table.add_row(*row_values)

            console.print(table)

            if len(results) > 20:
                console.print(
                    f"[secondary]… and {len(results) - 20} more rows[/secondary]"
                )
        else:
            # Simple list display
            for i, item in enumerate(results[:20], 1):
                console.print(f"{i}. {item}")

            if len(results) > 20:
                console.print(
                    f"[secondary]… and {len(results) - 20} more items[/secondary]"
                )

    else:
        # Fallback to JSON-like display
        console.print_json(data=results)


# One mark for each kind of message, coloured; the message itself is not.
# The TUI's builder marks a campaign's check the same way (interfaces.checks).


def display_success(message: str) -> None:
    """``✓ message``: something done, or a check passed."""
    console.print(f"[passed]✓[/passed] {message}")


def display_warning(message: str) -> None:
    """``! message``: worth knowing, not a failure."""
    console.print(f"[warning]![/warning] {message}")


def display_error(message: str) -> None:
    """``✗ message``: something that failed."""
    console.print(f"[failed]✗[/failed] {message}")


def display_info(message: str) -> None:
    """A message in passing."""
    console.print(f"[secondary]{message}[/secondary]")


def display_heading(title: str) -> None:
    """A section's title, with a blank line above it."""
    console.print(f"\n[heading]{title}[/heading]")


def display_hint(what: str, command: str) -> None:
    """What to do next, and the command that does it."""
    console.print(f"  [secondary]{what}:[/secondary] [accent]{command}[/accent]")


def confirm_action(message: str, default: bool = False) -> bool:
    """Get user confirmation for dangerous actions"""
    return click.confirm(message, default=default)


def format_duration(seconds: float) -> str:
    """Format duration in seconds to human readable format"""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}m"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}h"


def create_status_panel(title: str, content: str, status: str = "info") -> Panel:
    """Create a status panel with appropriate styling"""
    style_map = {
        "success": "passed",
        "error": "failed",
        "warning": "warning",
        "info": "accent",
    }

    style = style_map.get(status, "accent")
    return Panel(
        Text(content, style=style), title=title, border_style=style, padding=(1, 2)
    )


def launch_tui(cli_config, initial_tab: str = "dashboard", initial_data: dict = None):
    """Launch the TUI application with specified tab and optional initial data

    Args:
        cli_config: CLI configuration object
        initial_tab: Which tab to show initially (default: "dashboard")
        initial_data: Initial data to pre-fill in the tab (default: None)
    """
    try:
        from hackagent.interfaces.tui import HackAgentTUI

        app = HackAgentTUI(
            cli_config, initial_tab=initial_tab, initial_data=initial_data
        )
        app.run()

    except ImportError as e:
        raise Failed(
            "The terminal app needs its dependencies: pip install 'hackagent[tui]'"
        ) from e
    except Exception as e:
        raise Failed(f"The terminal app failed to start: {e}") from e
