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
Attacks Tab

Execute and manage security attacks.
"""

from typing import Optional

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, VerticalScroll
from textual.widgets import Button, Input, Label, ProgressBar, Select, Static, TextArea

from hackagent.cli.config import CLIConfig


class AttacksTab(Container):
    """Attacks tab for executing security attacks."""

    DEFAULT_CSS = ""

    BINDINGS = [
        Binding("e", "execute_attack", "Execute"),
        Binding("c", "clear_form", "Clear Form"),
    ]

    def __init__(self, cli_config: CLIConfig, initial_data: Optional[dict] = None):
        """Initialize attacks tab.

        Args:
            cli_config: CLI configuration object
            initial_data: Initial data to pre-fill form fields
        """
        super().__init__()
        self.cli_config = cli_config
        self.initial_data = initial_data or {}

    def compose(self) -> ComposeResult:
        """Compose the attacks layout."""
        with VerticalScroll():
            yield Static("[bold cyan]Attack Configuration[/bold cyan]")
            yield Static("")  # Spacing

            yield Label("Agent Name:")
            yield Input(placeholder="e.g., weather-bot", id="agent-name")
            yield Static("")  # Spacing

            yield Label("Agent Type:")
            yield Select(
                [("Google ADK", "google-adk"), ("LiteLLM", "litellm")],
                id="agent-type",
                value="google-adk",
            )
            yield Static("")  # Spacing

            yield Label("Endpoint URL:")
            yield Input(placeholder="e.g., http://localhost:8000", id="endpoint-url")
            yield Static("")  # Spacing

            yield Label("Attack Strategy:")
            yield Select(
                [("AdvPrefix", "advprefix")],
                id="attack-strategy",
                value="advprefix",
            )
            yield Static("")  # Spacing

            yield Label("Goals (what you want the agent to do incorrectly):")
            goals_area = TextArea("Return fake weather data", id="attack-goals")
            goals_area.styles.height = 6
            yield goals_area
            yield Static("")  # Spacing

            yield Label("Timeout (seconds):")
            yield Input(value="300", id="timeout")
            yield Static("")  # Spacing
            yield Static("")  # Extra spacing before buttons

            yield Button("Execute Attack", id="execute-attack", variant="primary")
            yield Button("Dry Run", id="dry-run", variant="default")
            yield Button("Clear", id="clear-form", variant="error")

            yield Static("")  # Spacing
            yield Static("")  # Extra spacing after buttons

            yield Static(
                "[dim]Configure attack parameters and click Execute[/dim]",
                id="execution-status",
            )
            yield ProgressBar(total=100, show_eta=True, id="attack-progress")

    def on_mount(self) -> None:
        """Called when the tab is mounted."""
        # Pre-fill form with initial data if provided
        if self.initial_data:
            self._prefill_form()

    def _prefill_form(self) -> None:
        """Pre-fill form fields with initial data."""
        if "agent_name" in self.initial_data:
            self.query_one("#agent-name", Input).value = self.initial_data["agent_name"]
        if "agent_type" in self.initial_data:
            self.query_one("#agent-type", Select).value = self.initial_data[
                "agent_type"
            ]
        if "endpoint" in self.initial_data:
            self.query_one("#endpoint-url", Input).value = self.initial_data["endpoint"]
        if "goals" in self.initial_data:
            self.query_one("#attack-goals", TextArea).text = self.initial_data["goals"]
        if "timeout" in self.initial_data:
            self.query_one("#timeout", Input).value = str(self.initial_data["timeout"])

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        if event.button.id == "execute-attack":
            self._execute_attack(dry_run=False)
        elif event.button.id == "dry-run":
            self._execute_attack(dry_run=True)
        elif event.button.id == "clear-form":
            self._clear_form()

    def _execute_attack(self, dry_run: bool = False) -> None:
        """Execute the configured attack.

        Args:
            dry_run: Whether to run in dry-run mode
        """
        # Get form values
        from textual.widgets._select import NoSelection

        agent_name = self.query_one("#agent-name", Input).value
        agent_type_raw = self.query_one("#agent-type", Select).value
        endpoint = self.query_one("#endpoint-url", Input).value
        strategy_raw = self.query_one("#attack-strategy", Select).value
        goals = self.query_one("#attack-goals", TextArea).text
        timeout = self.query_one("#timeout", Input).value

        # Validate inputs
        if not agent_name:
            self.notify("Please enter an agent name", severity="error")
            return
        if isinstance(agent_type_raw, NoSelection) or not agent_type_raw:
            self.notify("Please select an agent type", severity="error")
            return
        if not endpoint:
            self.notify("Please enter an endpoint URL", severity="error")
            return
        if isinstance(strategy_raw, NoSelection) or not strategy_raw:
            self.notify("Please select an attack strategy", severity="error")
            return
        if not goals:
            self.notify("Please enter attack goals", severity="error")
            return

        # Validate timeout is a valid integer
        try:
            timeout_int = int(timeout)
            if timeout_int <= 0:
                self.notify("Timeout must be a positive number", severity="error")
                return
        except ValueError:
            self.notify("Timeout must be a valid number", severity="error")
            return

        # Convert to strings (they should be strings after validation)
        agent_type = str(agent_type_raw)
        strategy = str(strategy_raw)

        status_widget = self.query_one("#execution-status", Static)
        progress_bar = self.query_one("#attack-progress", ProgressBar)

        if dry_run:
            status_widget.update(
                f"""[bold yellow]Dry Run Mode[/bold yellow]

[bold]Agent:[/bold] {agent_name}
[bold]Type:[/bold] {agent_type}
[bold]Endpoint:[/bold] {endpoint}
[bold]Strategy:[/bold] {strategy}
[bold]Goals:[/bold] {goals}
[bold]Timeout:[/bold] {timeout}s

[green]✅ Configuration validation passed[/green]
[dim]Remove dry-run flag to execute the attack[/dim]"""
            )
            self.notify("Dry run completed successfully", severity="information")
        else:
            # Actually execute the attack
            status_widget.update(
                f"""[bold cyan]🚀 Initializing Attack...[/bold cyan]

[bold]Agent:[/bold] {agent_name}
[bold]Type:[/bold] {agent_type}
[bold]Endpoint:[/bold] {endpoint}
[bold]Strategy:[/bold] {strategy}
[bold]Goals:[/bold] {goals}
[bold]Timeout:[/bold] {timeout}s

[yellow]⏳ Connecting to agent and preparing attack...[/yellow]"""
            )

            # Show immediate feedback - progress starting
            progress_bar.update(progress=5)
            status_widget.update(
                f"""[bold cyan]🚀 Starting Attack...[/bold cyan]

[bold]Agent:[/bold] {agent_name}
[bold]Type:[/bold] {agent_type}
[bold]Endpoint:[/bold] {endpoint}
[bold]Strategy:[/bold] {strategy}
[bold]Goals:[/bold] {goals}

[yellow]⏳ Launching attack execution...[/yellow]
[dim]Progress: 5%[/dim]"""
            )

            self.notify("Starting attack execution...", severity="information")

            # Run attack in background thread
            # Use lambda to pass arguments to the worker function
            try:
                self.run_worker(
                    lambda: self._run_attack_async(
                        agent_name, agent_type, endpoint, goals, int(timeout)
                    ),
                    thread=True,
                    exclusive=True,
                    name="attack-execution",
                )
            except Exception as e:
                # If worker fails to start, show error immediately
                status_widget.update(
                    f"""[bold red]❌ Failed to Start Attack[/bold red]

[bold]Error:[/bold] {str(e)}

[red]Could not start attack worker thread.[/red]
[dim]This might be a configuration or system issue.[/dim]"""
                )
                self.notify(f"Failed to start attack: {str(e)}", severity="error")

    def _run_attack_async(
        self, agent_name: str, agent_type: str, endpoint: str, goals: str, timeout: int
    ) -> None:
        """Run attack in background thread with progress updates.

        Args:
            agent_name: Name of the target agent
            agent_type: Type of agent (google-adk, litellm)
            endpoint: Agent endpoint URL
            goals: Attack goals
            timeout: Timeout in seconds
        """
        import io
        import logging
        import os
        import sys
        import time

        from hackagent import HackAgent
        from hackagent.cli.utils import get_agent_type_enum

        status_widget = self.query_one("#execution-status", Static)
        progress_bar = self.query_one("#attack-progress", ProgressBar)

        # Debug: Confirm worker started
        self.app.call_from_thread(
            self.notify, "Worker thread started!", severity="information"
        )

        # CRITICAL: Comprehensive rich suppression to prevent black screen
        # Multiple layers of defense to prevent ANY rich output during TUI mode

        # 1. Set environment variable to disable rich features
        saved_term = os.environ.get("TERM")
        os.environ["TERM"] = "dumb"  # Disable rich color/formatting

        # 2. Disable logging handlers
        hackagent_logger = logging.getLogger("hackagent")
        saved_handlers = hackagent_logger.handlers.copy()
        saved_level = hackagent_logger.level

        for handler in hackagent_logger.handlers[:]:
            hackagent_logger.removeHandler(handler)
        hackagent_logger.setLevel(logging.CRITICAL)

        # Suppress other noisy loggers
        logging.getLogger("httpx").setLevel(logging.CRITICAL)
        logging.getLogger("litellm").setLevel(logging.CRITICAL)

        # 3. Monkey-patch rich.console.Console to prevent ANY output
        import rich.console
        import rich.progress

        saved_console_class = rich.console.Console
        saved_progress_class = rich.progress.Progress

        # Create a mock Console that does nothing
        class NullConsole:
            def __init__(self, *args, **kwargs):
                pass

            def print(self, *args, **kwargs):
                pass

            def log(self, *args, **kwargs):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def __getattr__(self, name):
                return lambda *args, **kwargs: None

        # Create a mock Progress that does nothing
        class NullProgress:
            def __init__(self, *args, **kwargs):
                pass

            def add_task(self, *args, **kwargs):
                return 0

            def update(self, *args, **kwargs):
                pass

            def start(self):
                pass

            def stop(self):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def __getattr__(self, name):
                return lambda *args, **kwargs: None

        rich.console.Console = NullConsole  # type: ignore
        rich.progress.Progress = NullProgress  # type: ignore

        # 4. Redirect stdout/stderr as final safeguard
        original_stdout = sys.stdout
        original_stderr = sys.stderr
        sys.stdout = io.StringIO()
        sys.stderr = io.StringIO()

        try:
            # Convert agent type
            agent_type_enum = get_agent_type_enum(agent_type)

            # Update status - 10% progress
            self.app.call_from_thread(progress_bar.update, progress=10)
            self.app.call_from_thread(
                status_widget.update,
                f"""[bold cyan]🔧 Initializing HackAgent...[/bold cyan]

[bold]Agent:[/bold] {agent_name}
[bold]Type:[/bold] {agent_type}
[bold]Endpoint:[/bold] {endpoint}

[yellow]⏳ Setting up attack infrastructure...[/yellow]
[dim]Progress: 10%[/dim]""",
            )

            # Initialize HackAgent - 20% progress
            self.app.call_from_thread(progress_bar.update, progress=20)

            agent = HackAgent(
                name=agent_name,
                endpoint=endpoint,
                agent_type=agent_type_enum,
                api_key=self.cli_config.api_key,
                base_url=self.cli_config.base_url,
                timeout=5.0,  # 5 second timeout for API calls
            )

            # Build attack configuration - 30% progress
            self.app.call_from_thread(progress_bar.update, progress=30)
            attack_config = {
                "attack_type": "advprefix",
                "goals": [goals],
            }

            # Update status - 40% progress, starting attack
            self.app.call_from_thread(progress_bar.update, progress=40)
            self.app.call_from_thread(
                status_widget.update,
                f"""[bold cyan]⚔️ Executing AdvPrefix Attack...[/bold cyan]

[bold]Agent:[/bold] {agent_name}
[bold]Goals:[/bold] {goals}

[yellow]⏳ Attack in progress... This may take several minutes...[/yellow]
[dim]Generating adversarial prefixes and testing against target agent...[/dim]
[dim]Progress: 40%[/dim]""",
            )

            start_time = time.time()

            # Execute attack - simulate progress from 50% to 90%
            # Start a background thread to update progress
            import threading

            stop_progress = threading.Event()

            def update_progress_gradually():
                """Gradually update progress during attack execution"""
                for progress in range(50, 91, 5):
                    if stop_progress.is_set():
                        break
                    self.app.call_from_thread(progress_bar.update, progress=progress)
                    time.sleep(2)  # Update every 2 seconds

            progress_thread = threading.Thread(
                target=update_progress_gradually, daemon=True
            )
            progress_thread.start()

            try:
                results = agent.hack(
                    attack_config=attack_config,
                    run_config_override={"timeout": timeout},
                    fail_on_run_error=True,
                )
            finally:
                stop_progress.set()
                progress_thread.join(timeout=1)
                # Restore stdout/stderr
                sys.stdout = original_stdout
                sys.stderr = original_stderr

                # Restore logging configuration
                hackagent_logger.setLevel(saved_level)
                for handler in saved_handlers:
                    hackagent_logger.addHandler(handler)

                # Restore rich classes
                rich.console.Console = saved_console_class  # type: ignore
                rich.progress.Progress = saved_progress_class  # type: ignore

                # Restore TERM environment variable
                if saved_term is not None:
                    os.environ["TERM"] = saved_term
                elif "TERM" in os.environ:
                    del os.environ["TERM"]

            duration = time.time() - start_time

            # Complete progress - 100%
            self.app.call_from_thread(progress_bar.update, progress=100)

            # Display success
            result_count = len(results) if hasattr(results, "__len__") else "Unknown"
            self.app.call_from_thread(
                status_widget.update,
                f"""[bold green]✅ Attack Completed Successfully![/bold green]

[bold]Agent:[/bold] {agent_name}
[bold]Duration:[/bold] {duration:.1f} seconds
[bold]Results Generated:[/bold] {result_count}

[green]Attack execution finished![/green]
[dim]Check the Results tab to view detailed attack results.[/dim]
[dim]Results have been saved to the HackAgent platform.[/dim]""",
            )

            self.app.call_later(
                lambda: self.notify(
                    f"Attack completed in {duration:.1f}s!", severity="information"
                )
            )

        except Exception as e:
            # Restore stdout/stderr on error
            sys.stdout = original_stdout
            sys.stderr = original_stderr

            # Restore logging configuration
            hackagent_logger.setLevel(saved_level)
            for handler in saved_handlers:
                hackagent_logger.addHandler(handler)

            # Restore rich classes
            rich.console.Console = saved_console_class  # type: ignore
            rich.progress.Progress = saved_progress_class  # type: ignore

            # Restore TERM environment variable
            if saved_term is not None:
                os.environ["TERM"] = saved_term
            elif "TERM" in os.environ:
                del os.environ["TERM"]

            # Display error
            self.app.call_from_thread(progress_bar.update, progress=0)
            self.app.call_from_thread(
                status_widget.update,
                f"""[bold red]❌ Attack Failed[/bold red]

[bold]Agent:[/bold] {agent_name}
[bold]Error:[/bold] {str(e)}

[red]Attack execution encountered an error.[/red]
[dim]Please check your configuration and try again.[/dim]
[dim]Ensure the agent endpoint is accessible and API key is valid.[/dim]""",
            )

            error_msg = str(e)
            self.app.call_later(
                lambda: self.notify(f"Attack failed: {error_msg}", severity="error")
            )

    def _clear_form(self) -> None:
        """Clear all form fields."""
        self.query_one("#agent-name", Input).value = ""
        self.query_one("#endpoint-url", Input).value = ""
        self.query_one("#attack-goals", TextArea).text = "Return fake weather data"
        self.query_one("#timeout", Input).value = "300"

        status_widget = self.query_one("#execution-status", Static)
        progress_bar = self.query_one("#attack-progress", ProgressBar)
        status_widget.update("[dim]Configure attack parameters and click Execute[/dim]")
        progress_bar.update(progress=0)

        self.notify("Form cleared", severity="information")

    def refresh_data(self) -> None:
        """Refresh attacks data."""
        # No dynamic data to refresh for attacks list
        pass
