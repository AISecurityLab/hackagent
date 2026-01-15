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
from textual.containers import Container, Horizontal, VerticalScroll
from textual.widgets import (
    Button,
    Input,
    Label,
    ProgressBar,
    RichLog,
    Select,
    Static,
    TabbedContent,
    TabPane,
    TextArea,
)

from hackagent.cli.config import CLIConfig
from hackagent.cli.tui.widgets.actions import AgentActionsViewer
from hackagent.cli.tui.widgets.logs import AttackLogViewer


class AttacksTab(Container):
    """Attacks tab for executing security attacks."""

    DEFAULT_CSS = """
    AttacksTab {
        layout: horizontal;
    }

    AttacksTab #attack-form-container {
        width: 30%;
        border-right: solid $primary;
        padding: 1 2;
    }

    AttacksTab #attack-monitor-container {
        width: 70%;
    }
    """

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
        # Split layout: Left side for form, Right side for logs
        with Horizontal():
            # Left side: Attack configuration form
            with VerticalScroll(id="attack-form-container"):
                yield Static("[bold cyan]Attack Configuration[/bold cyan]")
                yield Static("")  # Spacing

                yield Label("Agent Name:")
                yield Input(placeholder="e.g., weather-bot", id="agent-name")
                yield Static("")  # Spacing

                yield Label("Agent Type:")
                yield Select(
                    [
                        ("Google ADK", "google-adk"),
                        ("LiteLLM", "litellm"),
                        ("LangChain", "langchain"),
                        ("OpenAI SDK", "openai-sdk"),
                        ("MCP", "mcp"),
                        ("A2A", "a2a"),
                    ],
                    id="agent-type",
                    value="google-adk",
                )
                yield Static("")  # Spacing

                yield Label("Endpoint URL:")
                yield Input(
                    placeholder="e.g., http://localhost:8000", id="endpoint-url"
                )
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

            # Right side: Tabbed monitor with logs and actions
            with Container(id="attack-monitor-container"):
                with TabbedContent():
                    with TabPane("📋 Logs", id="logs-tab"):
                        yield AttackLogViewer(
                            title="Attack Execution Logs",
                            show_controls=True,
                            max_lines=1000,
                            id="attack-log-viewer",
                        )
                    with TabPane("🔧 Actions", id="actions-tab"):
                        yield AgentActionsViewer(
                            title="Agent Actions Inspector",
                            show_controls=True,
                            id="attack-actions-viewer",
                        )

    def on_mount(self) -> None:
        """Called when the tab is mounted."""
        # Pre-fill form with initial data if provided
        if self.initial_data:
            self._prefill_form()

        # Add initial messages after a short delay to ensure widgets are ready
        self.call_after_refresh(self._add_initial_messages)

    def _add_initial_messages(self) -> None:
        """Add initial welcome messages to the viewers."""
        try:
            log_viewer = self.query_one("#attack-log-viewer", AttackLogViewer)
            actions_viewer = self.query_one(
                "#attack-actions-viewer", AgentActionsViewer
            )

            # Get the RichLog directly to verify it exists
            try:
                rich_log = log_viewer.query_one("#attack-log-display", RichLog)
                # Directly write to RichLog to test visibility
                rich_log.write("[bold cyan]📋 Attack Log Viewer Ready[/bold cyan]")
                rich_log.write(
                    "[yellow]Configure your attack and click Execute to begin[/yellow]"
                )
            except Exception:
                pass

            # Try actions viewer
            try:
                actions_log = actions_viewer.query_one("#actions-display", RichLog)
                actions_log.write(
                    "[bold green]🔧 Agent Actions Inspector Ready[/bold green]"
                )
                actions_log.write(
                    "[dim]Agent actions will appear here during execution[/dim]"
                )
            except Exception:
                pass

        except Exception:
            # If widgets aren't ready yet, skip initial messages
            pass

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
            return
        if isinstance(agent_type_raw, NoSelection) or not agent_type_raw:
            return
        if not endpoint:
            return
        if isinstance(strategy_raw, NoSelection) or not strategy_raw:
            return
        if not goals:
            return

        # Validate timeout is a valid integer
        try:
            timeout_int = int(timeout)
            if timeout_int <= 0:
                return
        except ValueError:
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
        log_viewer = self.query_one("#attack-log-viewer", AttackLogViewer)
        actions_viewer = self.query_one("#attack-actions-viewer", AgentActionsViewer)

        # Clear previous logs and actions
        self.app.call_from_thread(log_viewer.clear_logs)
        self.app.call_from_thread(actions_viewer.clear_actions)
        self.app.call_from_thread(
            log_viewer.add_log,
            f"🚀 Starting attack execution for agent: {agent_name}",
            "INFO",
        )
        self.app.call_from_thread(
            actions_viewer.add_step_separator,
            f"Attack Initialization: {agent_name}",
            1,
        )

        # CRITICAL: Comprehensive rich suppression to prevent black screen
        # Multiple layers of defense to prevent ANY rich output during TUI mode

        # 1. Set environment variable to disable rich features
        saved_term = os.environ.get("TERM")
        os.environ["TERM"] = "dumb"  # Disable rich color/formatting

        # 2. Set up custom logging handlers for TUI
        hackagent_logger = logging.getLogger("hackagent")
        saved_handlers = hackagent_logger.handlers.copy()
        saved_level = hackagent_logger.level

        # Remove existing handlers
        for handler in hackagent_logger.handlers[:]:
            hackagent_logger.removeHandler(handler)

        # Add TUI-specific handlers
        from hackagent.cli.tui.logger import TUILogHandler

        # Handler for log messages
        tui_log_handler = TUILogHandler(
            app=self.app,
            callback=log_viewer.add_log,
            level=logging.INFO,
        )
        hackagent_logger.addHandler(tui_log_handler)
        hackagent_logger.setLevel(logging.INFO)

        # Suppress other noisy loggers
        logging.getLogger("httpx").setLevel(logging.CRITICAL)
        logging.getLogger("litellm").setLevel(logging.CRITICAL)

        # 3. Disable Rich progress bars by setting environment variable
        # This prevents Rich from trying to use terminal features that conflict with TUI
        os.environ["FORCE_COLOR"] = "0"
        os.environ["NO_COLOR"] = "1"

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

            # Set up TUI logging callback
            def log_callback(message: str, level: str) -> None:
                """Callback for TUI log handler"""
                log_viewer.add_log(message, level)

            # Create and attach TUI log handler to the attack
            # This will be picked up by the @with_tui_logging decorator

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

            # Attach TUI log handler before execution
            # The attack strategy will internally call the attack class's run() method
            # which has the @with_tui_logging decorator
            try:
                # Note: We need to access the attack instance to attach the handler
                # This will be done by modifying the agent.hack() flow or by
                # directly accessing the attack strategy instance

                # For now, we'll execute the attack and the decorator will handle logging
                # The handler attachment needs to happen in the strategy execution
                results = agent.hack(
                    attack_config=attack_config,
                    run_config_override={"timeout": timeout},
                    fail_on_run_error=True,
                    # Pass TUI context for logging
                    _tui_app=self.app,
                    _tui_log_callback=log_callback,
                )
            finally:
                stop_progress.set()
                progress_thread.join(timeout=1)
                # Restore stdout/stderr
                sys.stdout = original_stdout
                sys.stderr = original_stderr

                # Remove TUI handler from all loggers
                if tui_log_handler in hackagent_logger.handlers:
                    hackagent_logger.removeHandler(tui_log_handler)

                # Restore logging configuration
                hackagent_logger.setLevel(saved_level)
                for handler in saved_handlers:
                    hackagent_logger.addHandler(handler)

                # Restore environment variables
                if saved_term is not None:
                    os.environ["TERM"] = saved_term
                elif "TERM" in os.environ:
                    del os.environ["TERM"]

                if "FORCE_COLOR" in os.environ:
                    del os.environ["FORCE_COLOR"]
                if "NO_COLOR" in os.environ:
                    del os.environ["NO_COLOR"]

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

        except Exception as e:
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

        finally:
            # Always restore stdout/stderr and clean up handlers
            sys.stdout = original_stdout
            sys.stderr = original_stderr

            # Remove TUI handler from all loggers
            try:
                if tui_log_handler in hackagent_logger.handlers:
                    hackagent_logger.removeHandler(tui_log_handler)
            except Exception:
                pass  # Handler cleanup errors shouldn't fail silently

            # Restore logging configuration
            hackagent_logger.setLevel(saved_level)
            for handler in saved_handlers:
                hackagent_logger.addHandler(handler)

            # Restore environment variables
            if saved_term is not None:
                os.environ["TERM"] = saved_term
            elif "TERM" in os.environ:
                del os.environ["TERM"]

            if "FORCE_COLOR" in os.environ:
                del os.environ["FORCE_COLOR"]
            if "NO_COLOR" in os.environ:
                del os.environ["NO_COLOR"]

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

    def refresh_data(self) -> None:
        """Refresh attacks data."""
        # No dynamic data to refresh for attacks list
        pass
