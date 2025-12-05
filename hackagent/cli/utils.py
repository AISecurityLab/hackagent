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
CLI Utilities

Common utilities for the HackAgent CLI including error handling,
formatting, and helper functions.
"""

import functools
import json
from pathlib import Path
from typing import Any, Dict

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.traceback import Traceback

from hackagent.errors import ApiError, HackAgentError

console = Console()


def handle_errors(func):
    """Decorator for consistent error handling across CLI commands"""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except HackAgentError as e:
            console.print(f"[bold red]❌ HackAgent Error: {str(e)}")
            if console._environ.get("HACKAGENT_DEBUG"):
                console.print(Traceback())
            raise click.ClickException(str(e))
        except ApiError as e:
            console.print(f"[bold red]❌ API Error: {str(e)}")
            if console._environ.get("HACKAGENT_DEBUG"):
                console.print(Traceback())
            raise click.ClickException(str(e))
        except ValueError as e:
            console.print(f"[bold red]❌ Configuration Error: {str(e)}")
            raise click.ClickException(str(e))
        except FileNotFoundError as e:
            console.print(f"[bold red]❌ File Not Found: {str(e)}")
            raise click.ClickException(str(e))
        except Exception as e:
            console.print(f"[bold red]❌ Unexpected error: {str(e)}")
            if console._environ.get("HACKAGENT_DEBUG"):
                console.print(Traceback())
            raise click.ClickException(str(e))

    return wrapper


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
                    raise click.ClickException(
                        "PyYAML required for YAML config files. Install with: pip install pyyaml"
                    )
            else:
                return json.load(f)
    except json.JSONDecodeError as e:
        raise click.ClickException(f"Invalid JSON in config file {path}: {e}")
    except Exception as e:
        raise click.ClickException(f"Failed to load config file {path}: {e}")


def display_results_table(results: Any, title: str = "Results") -> None:
    """Display results in a formatted table"""
    import pandas as pd

    if isinstance(results, pd.DataFrame):
        if results.empty:
            console.print(f"[yellow]ℹ️ No {title.lower()} found")
            return

        table = Table(title=title, show_header=True, header_style="bold cyan")

        # Add columns
        for column in results.columns:
            table.add_column(str(column))

        # Add rows (limit to first 20 for display)
        display_results = results.head(20)
        for _, row in display_results.iterrows():
            table.add_row(*[str(value) for value in row])

        console.print(table)

        if len(results) > 20:
            console.print(f"[dim]... and {len(results) - 20} more rows")

    elif isinstance(results, list):
        if not results:
            console.print(f"[yellow]ℹ️ No {title.lower()} found")
            return

        # Try to create table from list of dicts
        if results and isinstance(results[0], dict):
            table = Table(title=title, show_header=True, header_style="bold cyan")

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
                console.print(f"[dim]... and {len(results) - 20} more rows")
        else:
            # Simple list display
            for i, item in enumerate(results[:20], 1):
                console.print(f"{i}. {item}")

            if len(results) > 20:
                console.print(f"[dim]... and {len(results) - 20} more items")

    else:
        # Fallback to JSON-like display
        console.print_json(data=results)


def display_success(message: str) -> None:
    """Display success message with formatting"""
    console.print(f"[bold green]✅ {message}")


def display_warning(message: str) -> None:
    """Display warning message with formatting"""
    console.print(f"[bold yellow]⚠️ {message}")


def display_error(message: str) -> None:
    """Display error message with formatting"""
    console.print(f"[bold red]❌ {message}")


def display_info(message: str) -> None:
    """Display info message with formatting"""
    console.print(f"[cyan]ℹ️ {message}")


def confirm_action(message: str, default: bool = False) -> bool:
    """Get user confirmation for dangerous actions"""
    return click.confirm(f"⚠️ {message}", default=default)


def get_agent_type_enum(agent_type: str):
    """Convert string agent type to AgentTypeEnum"""
    from hackagent.router.types import AgentTypeEnum

    # Normalize the input
    normalized = agent_type.upper().replace("-", "_").replace(" ", "_")

    # Map common variations
    type_mapping = {
        "GOOGLE_ADK": AgentTypeEnum.GOOGLE_ADK,
        "GOOGLE-ADK": AgentTypeEnum.GOOGLE_ADK,
        "ADK": AgentTypeEnum.GOOGLE_ADK,
        "LANGCHAIN": AgentTypeEnum.LANGCHAIN,
        "LANG_CHAIN": AgentTypeEnum.LANGCHAIN,
        "LITELLM": AgentTypeEnum.LITELLM,
        "LITE_LLM": AgentTypeEnum.LITELLM,
        "OPENAI_SDK": AgentTypeEnum.OPENAI_SDK,
        "OPENAI-SDK": AgentTypeEnum.OPENAI_SDK,
        "OPENAI": AgentTypeEnum.OPENAI_SDK,
        "OTHER": AgentTypeEnum.UNKNOWN,
        "UNKNOWN": AgentTypeEnum.UNKNOWN,
    }

    if normalized in type_mapping:
        return type_mapping[normalized]

    try:
        return AgentTypeEnum(normalized)
    except ValueError:
        # If the type is not recognized, fallback to UNKNOWN
        console.print(
            f"[yellow]⚠️ Agent type '{agent_type}' not recognized, using 'UNKNOWN'[/yellow]"
        )
        return AgentTypeEnum.UNKNOWN


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
        "success": "green",
        "error": "red",
        "warning": "yellow",
        "info": "cyan",
    }

    style = style_map.get(status, "cyan")
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
        from hackagent.cli.tui import HackAgentTUI

        app = HackAgentTUI(
            cli_config, initial_tab=initial_tab, initial_data=initial_data
        )
        app.run()

    except ImportError:
        console.print("[bold red]❌ TUI dependencies not installed[/bold red]")
        console.print("\n[cyan]💡 Install with:[/cyan]")
        console.print("  uv add textual")
        raise click.ClickException("TUI dependencies not installed")
    except Exception as e:
        console.print(f"[bold red]❌ TUI failed to start: {e}[/bold red]")
        raise click.ClickException(f"TUI failed to start: {e}")
