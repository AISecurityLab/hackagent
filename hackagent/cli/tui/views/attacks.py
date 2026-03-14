# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Attacks Tab

Execute and manage security attacks with dynamic, strategy-aware configuration.
"""

from typing import Any, Dict, List, Optional

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.widgets import (
    Button,
    Checkbox,
    Collapsible,
    Input,
    Label,
    ProgressBar,
    RichLog,
    Select,
    Static,
    Switch,
    TabbedContent,
    TabPane,
    TextArea,
)

from hackagent.cli.config import CLIConfig
from hackagent.cli.tui.attack_specs import (
    AttackConfigSpec,
    ConfigField,
    FieldType,
    get_all_attack_specs,
    get_attack_config_spec,
)
from hackagent.cli.tui.widgets.actions import AgentActionsViewer
from hackagent.cli.tui.widgets.logs import AttackLogViewer


def _escape(value: Any) -> str:
    """Escape a value for safe Rich markup rendering.

    Args:
        value: Any value to escape

    Returns:
        String with Rich markup characters escaped

    Note:
        We escape ALL square brackets, not just tag-like patterns,
        because Rich's markup parser can get confused by unescaped
        brackets in certain contexts (e.g., JSON arrays inside colored text).
    """
    if value is None:
        return ""
    text = str(value)
    return text.replace("[", "\\[").replace("]", "\\]")


# =====================================================================
# Strategy-specific config field IDs use the prefix ``cfg-`` so we can
# query them without colliding with the static form fields.
# =====================================================================
_CFG_PREFIX = "cfg-"


def _field_widget_id(field: ConfigField) -> str:
    """Return the Textual widget ID for a config field."""
    return f"{_CFG_PREFIX}{field.key.replace('.', '-')}"


class AttacksTab(Container):
    """Attacks tab for executing security attacks with dynamic config."""

    DEFAULT_CSS = """
    AttacksTab {
        layout: horizontal;
    }

    AttacksTab #attack-form-container {
        width: 35%;
        border-right: solid $primary;
        padding: 1 2;
    }

    AttacksTab #attack-monitor-container {
        width: 65%;
    }

    AttacksTab .section-title {
        color: $text;
        text-style: bold;
        margin-top: 1;
    }

    AttacksTab .field-description {
        color: $text-muted;
        margin-bottom: 1;
    }

    AttacksTab #strategy-description {
        color: $text-muted;
        margin-bottom: 1;
    }

    AttacksTab .advanced-toggle {
        margin-top: 1;
    }

    AttacksTab .validation-errors {
        color: $error;
        margin-top: 1;
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
        self._show_advanced = False
        self._current_spec: Optional[AttackConfigSpec] = None

    def compose(self) -> ComposeResult:
        """Compose the attacks layout."""
        # Build strategy choices from the registry
        all_specs = get_all_attack_specs()
        strategy_choices: List[tuple] = [
            (spec.display_name, spec.technique_key) for spec in all_specs.values()
        ]
        default_strategy = strategy_choices[0][1] if strategy_choices else "advprefix"

        with Horizontal():
            # ── Left side: Attack configuration form ──
            with VerticalScroll(id="attack-form-container"):
                yield Static("[bold cyan]⚔️  Attack Configuration[/bold cyan]")
                yield Static("")

                # --- Agent settings (always shown) ---
                yield Label("Agent Name:")
                yield Input(placeholder="e.g., weather-bot", id="agent-name")
                yield Static("")

                yield Label("Agent Type:")
                yield Select(
                    [
                        ("Google ADK", "google-adk"),
                        ("LiteLLM", "litellm"),
                        ("LangChain", "langchain"),
                        ("OpenAI SDK", "openai-sdk"),
                        ("Ollama", "ollama"),
                        ("MCP", "mcp"),
                        ("A2A", "a2a"),
                    ],
                    id="agent-type",
                    value="google-adk",
                )
                yield Static("")

                yield Label("Endpoint URL:")
                yield Input(
                    placeholder="e.g., http://localhost:8000", id="endpoint-url"
                )
                yield Static("")

                yield Label("Goals (what you want the agent to do incorrectly):")
                goals_area = TextArea("Return fake weather data", id="attack-goals")
                goals_area.styles.height = 5
                yield goals_area
                yield Static("")

                yield Label("Timeout (seconds):")
                yield Input(value="300", id="timeout")
                yield Static("")

                # --- Strategy selector ---
                yield Static("[bold]Attack Strategy[/bold]", classes="section-title")
                yield Select(
                    strategy_choices,
                    id="attack-strategy",
                    value=default_strategy,
                )
                yield Static("", id="strategy-description")
                yield Static("")

                # --- Dynamic config container (populated on strategy change) ---
                yield Vertical(id="strategy-config-container")

                # --- Advanced toggle ---
                yield Checkbox(
                    "Show advanced settings",
                    id="advanced-toggle",
                    value=False,
                    classes="advanced-toggle",
                )
                yield Static("")

                # --- Validation errors ---
                yield Static("", id="validation-errors", classes="validation-errors")

                # --- Action buttons ---
                yield Button("Execute Attack", id="execute-attack", variant="primary")
                yield Button("Dry Run", id="dry-run", variant="default")
                yield Button("Reset Defaults", id="reset-defaults", variant="warning")
                yield Button("Clear", id="clear-form", variant="error")

                yield Static("")
                yield Static(
                    "[dim]Configure attack parameters and click Execute[/dim]",
                    id="execution-status",
                )
                yield ProgressBar(total=100, show_eta=True, id="attack-progress")

            # ── Right side: Tabbed monitor with logs and actions ──
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

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_mount(self) -> None:
        """Called when the tab is mounted."""
        if self.initial_data:
            self._prefill_form()

        self.call_after_refresh(self._add_initial_messages)

        # Render config fields for the default strategy
        strategy_select = self.query_one("#attack-strategy", Select)
        if strategy_select.value and not isinstance(
            strategy_select.value, type(Select.BLANK)
        ):
            self._render_strategy_config(str(strategy_select.value))

    def _add_initial_messages(self) -> None:
        """Add initial welcome messages to the viewers."""
        try:
            log_viewer = self.query_one("#attack-log-viewer", AttackLogViewer)
            try:
                rich_log = log_viewer.query_one("#attack-log-display", RichLog)
                rich_log.write("[bold cyan]📋 Attack Log Viewer Ready[/bold cyan]")
                rich_log.write(
                    "[yellow]Configure your attack and click Execute to begin[/yellow]"
                )
            except Exception:
                pass

            actions_viewer = self.query_one(
                "#attack-actions-viewer", AgentActionsViewer
            )
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
            pass

    # ------------------------------------------------------------------
    # Dynamic strategy config rendering
    # ------------------------------------------------------------------

    def on_select_changed(self, event: Select.Changed) -> None:
        """React to strategy selector changes."""
        if event.select.id == "attack-strategy":
            value = event.value
            if value and not isinstance(value, type(Select.BLANK)):
                self._render_strategy_config(str(value))

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        """React to the advanced toggle."""
        if event.checkbox.id == "advanced-toggle":
            self._show_advanced = event.value
            # Re-render with/without advanced fields
            if self._current_spec:
                self._render_strategy_config(self._current_spec.technique_key)

    def _render_strategy_config(self, technique_key: str) -> None:
        """Clear and re-render the strategy-specific config fields.

        Args:
            technique_key: Technique identifier (e.g. ``"advprefix"``).
        """
        spec = get_attack_config_spec(technique_key)
        if spec is None:
            return
        self._current_spec = spec

        # Update description
        desc_widget = self.query_one("#strategy-description", Static)
        desc_widget.update(f"[dim]{_escape(spec.description)}[/dim]")

        # Remove old config widgets
        container = self.query_one("#strategy-config-container", Vertical)
        container.remove_children()

        # Group fields by section
        for section in spec.sections():
            fields = spec.fields_for_section(
                section, include_advanced=self._show_advanced
            )
            if not fields:
                continue

            # Mount a collapsible section
            collapsible = Collapsible(title=section, collapsed=False)
            container.mount(collapsible)

            for cfg_field in fields:
                widget_id = _field_widget_id(cfg_field)
                # Label with optional tooltip
                label_text = cfg_field.label
                if cfg_field.required:
                    label_text += " *"
                collapsible.mount(Label(label_text))

                if cfg_field.description:
                    collapsible.mount(
                        Static(
                            f"[dim]{_escape(cfg_field.description)}[/dim]",
                            classes="field-description",
                        )
                    )

                # Render the appropriate widget
                widget = self._create_field_widget(cfg_field, widget_id)
                collapsible.mount(widget)

        # Clear validation errors
        self.query_one("#validation-errors", Static).update("")

    def _create_field_widget(self, cfg_field: ConfigField, widget_id: str) -> Any:
        """Create the appropriate Textual widget for a :class:`ConfigField`."""
        if cfg_field.field_type == FieldType.CHOICE:
            return Select(
                cfg_field.choices or [],
                id=widget_id,
                value=cfg_field.default,
            )

        if cfg_field.field_type == FieldType.BOOLEAN:
            return Switch(
                value=bool(cfg_field.default)
                if cfg_field.default is not None
                else False,
                id=widget_id,
            )

        if cfg_field.field_type == FieldType.TEXT:
            ta = TextArea(
                str(cfg_field.default) if cfg_field.default is not None else "",
                id=widget_id,
            )
            ta.styles.height = 4
            return ta

        # STRING / INTEGER / FLOAT → Input
        placeholder = ""
        if cfg_field.min_value is not None and cfg_field.max_value is not None:
            placeholder = f"{cfg_field.min_value} – {cfg_field.max_value}"
        elif cfg_field.field_type == FieldType.INTEGER:
            placeholder = "integer"
        elif cfg_field.field_type == FieldType.FLOAT:
            placeholder = "number"

        return Input(
            value=str(cfg_field.default) if cfg_field.default is not None else "",
            placeholder=placeholder,
            id=widget_id,
        )

    # ------------------------------------------------------------------
    # Collect values from dynamic config
    # ------------------------------------------------------------------

    def _collect_strategy_config(self) -> Dict[str, Any]:
        """Read all strategy-specific config field values from the UI.

        Returns:
            A flat ``{key: value}`` dict with parsed values.
        """
        if self._current_spec is None:
            return {}

        values: Dict[str, Any] = {}
        for cfg_field in self._current_spec.fields:
            if cfg_field.advanced and not self._show_advanced:
                # Use default for hidden advanced fields
                if cfg_field.default is not None:
                    values[cfg_field.key] = cfg_field.default
                continue

            widget_id = _field_widget_id(cfg_field)
            try:
                widget = self.query_one(f"#{widget_id}")
            except Exception:
                # Widget not mounted (e.g. section collapsed)
                if cfg_field.default is not None:
                    values[cfg_field.key] = cfg_field.default
                continue

            raw: Any = None
            if isinstance(widget, Select):
                raw = widget.value
                if isinstance(raw, type(Select.BLANK)):
                    raw = None
            elif isinstance(widget, Switch):
                raw = widget.value
            elif isinstance(widget, TextArea):
                raw = widget.text
            elif isinstance(widget, Input):
                raw = widget.value
            else:
                raw = getattr(widget, "value", None)

            # Cast to correct Python type
            if raw is not None and raw != "":
                if cfg_field.field_type == FieldType.INTEGER:
                    try:
                        raw = int(raw)
                    except (TypeError, ValueError):
                        pass
                elif cfg_field.field_type == FieldType.FLOAT:
                    try:
                        raw = float(raw)
                    except (TypeError, ValueError):
                        pass

            values[cfg_field.key] = raw

        return values

    def _expand_dotted_keys(self, flat: Dict[str, Any]) -> Dict[str, Any]:
        """Expand dotted keys like ``"attacker.model"`` into nested dicts.

        Example::

            {"attacker.model": "gpt-4", "n_iterations": 5}
            → {"attacker": {"model": "gpt-4"}, "n_iterations": 5}
        """
        result: Dict[str, Any] = {}
        for key, value in flat.items():
            parts = key.split(".")
            target = result
            for part in parts[:-1]:
                target = target.setdefault(part, {})
            target[parts[-1]] = value
        return result

    # ------------------------------------------------------------------
    # Form helpers
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Button handlers
    # ------------------------------------------------------------------

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        if event.button.id == "execute-attack":
            self._execute_attack(dry_run=False)
        elif event.button.id == "dry-run":
            self._execute_attack(dry_run=True)
        elif event.button.id == "clear-form":
            self._clear_form()
        elif event.button.id == "reset-defaults":
            self._reset_defaults()

    def _reset_defaults(self) -> None:
        """Reset strategy-specific fields to their defaults."""
        if self._current_spec:
            self._render_strategy_config(self._current_spec.technique_key)

    def _execute_attack(self, dry_run: bool = False) -> None:
        """Execute the configured attack.

        Args:
            dry_run: Whether to run in dry-run mode
        """
        from textual.widgets._select import NoSelection

        agent_name = self.query_one("#agent-name", Input).value
        agent_type_raw = self.query_one("#agent-type", Select).value
        endpoint = self.query_one("#endpoint-url", Input).value
        strategy_raw = self.query_one("#attack-strategy", Select).value
        goals = self.query_one("#attack-goals", TextArea).text
        timeout = self.query_one("#timeout", Input).value

        # ── Basic validation ──
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

        try:
            timeout_int = int(timeout)
            if timeout_int <= 0:
                return
        except ValueError:
            return

        agent_type = str(agent_type_raw)
        strategy = str(strategy_raw)

        # ── Collect & validate strategy-specific config ──
        strategy_values = self._collect_strategy_config()
        errors_widget = self.query_one("#validation-errors", Static)

        if self._current_spec:
            errors = self._current_spec.validate(strategy_values)
            if errors:
                errors_widget.update(
                    "[bold red]Validation errors:[/bold red]\n"
                    + "\n".join(f"  • {e}" for e in errors)
                )
                return

        errors_widget.update("")  # clear previous errors

        # Build the full attack config dict (nested)
        strategy_config = self._expand_dotted_keys(strategy_values)
        attack_config: Dict[str, Any] = {
            "attack_type": strategy,
            "goals": [goals],
            **strategy_config,
        }

        status_widget = self.query_one("#execution-status", Static)
        progress_bar = self.query_one("#attack-progress", ProgressBar)

        if dry_run:
            # Pretty-print the full config for review
            import json

            config_preview = json.dumps(attack_config, indent=2, default=str)
            status_widget.update(
                f"""[bold yellow]Dry Run Mode[/bold yellow]

[bold]Agent:[/bold] {_escape(agent_name)}
[bold]Type:[/bold] {_escape(agent_type)}
[bold]Endpoint:[/bold] {_escape(endpoint)}
[bold]Strategy:[/bold] {_escape(strategy)}
[bold]Goals:[/bold] {_escape(goals)}
[bold]Timeout:[/bold] {timeout}s

[bold]Full Attack Config:[/bold]
{_escape(config_preview)}

[green]✅ Configuration validation passed[/green]
[dim]Remove dry-run flag to execute the attack[/dim]"""
            )
        else:
            status_widget.update(
                f"""[bold cyan]🚀 Initializing Attack...[/bold cyan]

[bold]Agent:[/bold] {_escape(agent_name)}
[bold]Type:[/bold] {_escape(agent_type)}
[bold]Endpoint:[/bold] {_escape(endpoint)}
[bold]Strategy:[/bold] {_escape(strategy)}
[bold]Goals:[/bold] {_escape(goals)}
[bold]Timeout:[/bold] {timeout}s

[yellow]⏳ Connecting to agent and preparing attack...[/yellow]"""
            )

            progress_bar.update(progress=5)

            try:
                self.run_worker(
                    lambda: self._run_attack_async(
                        agent_name,
                        agent_type,
                        endpoint,
                        goals,
                        timeout_int,
                        attack_config,
                    ),
                    thread=True,
                    exclusive=True,
                    name="attack-execution",
                )
            except Exception as e:
                status_widget.update(
                    f"""[bold red]❌ Failed to Start Attack[/bold red]

[bold]Error:[/bold] {_escape(str(e))}

[red]Could not start attack worker thread.[/red]
[dim]This might be a configuration or system issue.[/dim]"""
                )

    def _run_attack_async(
        self,
        agent_name: str,
        agent_type: str,
        endpoint: str,
        goals: str,
        timeout: int,
        attack_config: Dict[str, Any],
    ) -> None:
        """Run attack in background thread with progress updates.

        Args:
            agent_name: Name of the target agent
            agent_type: Type of agent (google-adk, litellm, etc.)
            endpoint: Agent endpoint URL
            goals: Attack goals
            timeout: Timeout in seconds
            attack_config: Full attack configuration dict (already built)
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

        # Comprehensive rich suppression
        saved_term = os.environ.get("TERM")
        os.environ["TERM"] = "dumb"

        hackagent_logger = logging.getLogger("hackagent")
        saved_handlers = hackagent_logger.handlers.copy()
        saved_level = hackagent_logger.level

        for handler in hackagent_logger.handlers[:]:
            hackagent_logger.removeHandler(handler)

        from hackagent.cli.tui.logger import TUILogHandler

        tui_log_handler = TUILogHandler(
            app=self.app,
            callback=log_viewer.add_log,
            level=logging.INFO,
        )
        hackagent_logger.addHandler(tui_log_handler)
        hackagent_logger.setLevel(logging.INFO)

        logging.getLogger("httpx").setLevel(logging.CRITICAL)
        logging.getLogger("litellm").setLevel(logging.CRITICAL)

        os.environ["FORCE_COLOR"] = "0"
        os.environ["NO_COLOR"] = "1"

        original_stdout = sys.stdout
        original_stderr = sys.stderr
        sys.stdout = io.StringIO()
        sys.stderr = io.StringIO()

        try:
            agent_type_enum = get_agent_type_enum(agent_type)

            self.app.call_from_thread(progress_bar.update, progress=10)
            self.app.call_from_thread(
                status_widget.update,
                f"""[bold cyan]🔧 Initializing HackAgent...[/bold cyan]

[bold]Agent:[/bold] {_escape(agent_name)}
[bold]Type:[/bold] {_escape(agent_type)}
[bold]Endpoint:[/bold] {_escape(endpoint)}

[yellow]⏳ Setting up attack infrastructure...[/yellow]
[dim]Progress: 10%[/dim]""",
            )

            self.app.call_from_thread(progress_bar.update, progress=20)

            agent = HackAgent(
                name=agent_name,
                endpoint=endpoint,
                agent_type=agent_type_enum,
                api_key=self.cli_config.api_key,
                base_url=self.cli_config.base_url,
                timeout=5.0,
            )

            self.app.call_from_thread(progress_bar.update, progress=30)

            strategy_name = attack_config.get("attack_type", "unknown")
            self.app.call_from_thread(progress_bar.update, progress=40)
            self.app.call_from_thread(
                status_widget.update,
                f"""[bold cyan]⚔️ Executing {_escape(strategy_name)} Attack...[/bold cyan]

[bold]Agent:[/bold] {_escape(agent_name)}
[bold]Goals:[/bold] {_escape(goals)}

[yellow]⏳ Attack in progress... This may take several minutes...[/yellow]
[dim]Progress: 40%[/dim]""",
            )

            start_time = time.time()

            def log_callback(message: str, level: str) -> None:
                log_viewer.add_log(message, level)

            import threading

            stop_progress = threading.Event()

            def update_progress_gradually():
                for progress in range(50, 91, 5):
                    if stop_progress.is_set():
                        break
                    self.app.call_from_thread(progress_bar.update, progress=progress)
                    time.sleep(2)

            progress_thread = threading.Thread(
                target=update_progress_gradually, daemon=True
            )
            progress_thread.start()

            try:
                results = agent.hack(
                    attack_config=attack_config,
                    run_config_override={"timeout": timeout},
                    fail_on_run_error=True,
                    _tui_app=self.app,
                    _tui_log_callback=log_callback,
                )
            finally:
                stop_progress.set()
                progress_thread.join(timeout=1)
                sys.stdout = original_stdout
                sys.stderr = original_stderr

                if tui_log_handler in hackagent_logger.handlers:
                    hackagent_logger.removeHandler(tui_log_handler)

                hackagent_logger.setLevel(saved_level)
                for handler in saved_handlers:
                    hackagent_logger.addHandler(handler)

                if saved_term is not None:
                    os.environ["TERM"] = saved_term
                elif "TERM" in os.environ:
                    del os.environ["TERM"]

                if "FORCE_COLOR" in os.environ:
                    del os.environ["FORCE_COLOR"]
                if "NO_COLOR" in os.environ:
                    del os.environ["NO_COLOR"]

            duration = time.time() - start_time
            self.app.call_from_thread(progress_bar.update, progress=100)

            result_count = len(results) if hasattr(results, "__len__") else "Unknown"
            self.app.call_from_thread(
                status_widget.update,
                f"""[bold green]✅ Attack Completed Successfully![/bold green]

[bold]Agent:[/bold] {_escape(agent_name)}
[bold]Duration:[/bold] {duration:.1f} seconds
[bold]Results Generated:[/bold] {result_count}

[green]Attack execution finished![/green]
[dim]Check the Results tab to view detailed attack results.[/dim]
[dim]Results have been saved to the HackAgent platform.[/dim]""",
            )

        except Exception as e:
            self.app.call_from_thread(progress_bar.update, progress=0)
            self.app.call_from_thread(
                status_widget.update,
                f"""[bold red]❌ Attack Failed[/bold red]

[bold]Agent:[/bold] {_escape(agent_name)}
[bold]Error:[/bold] {_escape(str(e))}

[red]Attack execution encountered an error.[/red]
[dim]Please check your configuration and try again.[/dim]
[dim]Ensure the agent endpoint is accessible and API key is valid.[/dim]""",
            )

        finally:
            sys.stdout = original_stdout
            sys.stderr = original_stderr

            try:
                if tui_log_handler in hackagent_logger.handlers:
                    hackagent_logger.removeHandler(tui_log_handler)
            except Exception:
                pass

            hackagent_logger.setLevel(saved_level)
            for handler in saved_handlers:
                hackagent_logger.addHandler(handler)

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
        self.query_one("#validation-errors", Static).update("")

    def refresh_data(self) -> None:
        """Refresh attacks data."""
        pass
