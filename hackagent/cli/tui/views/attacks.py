# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Attacks Tab

Execute and manage security attacks with dynamic, strategy-aware configuration.
"""

import copy
from typing import Any, Dict, List, Optional

from textual import on
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
    RadioButton,
    RadioSet,
    RichLog,
    Select,
    Static,
    Switch,
    TabbedContent,
    TabPane,
    TextArea,
)

from hackagent.datasets.presets import PRESETS as _DATASET_PRESETS

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
_ROLE_COMBO_FIELDS = ("identifier", "endpoint", "api_key", "agent_type")
_COMMON_STATIC_ROLES = {"judge", "category_classifier"}

_DEFAULT_ATTACK_CONFIG_CACHE: Optional[Dict[str, Dict[str, Any]]] = None


def _field_widget_id(field: ConfigField) -> str:
    """Return the Textual widget ID for a config field."""
    return f"{_CFG_PREFIX}{field.key.replace('.', '-')}"


def _humanize_role_name(role: str) -> str:
    """Convert a role key into a human-readable role label."""
    title = role.replace("_", " ").title()
    return title.replace("Llm", "LLM")


def _looks_like_llm_role_config(value: Any) -> bool:
    """Heuristically determine whether a value is an LLM role config dict."""
    if not isinstance(value, dict):
        return False
    return any(key in value for key in _ROLE_COMBO_FIELDS)


def _load_attack_default_config_cache() -> Dict[str, Dict[str, Any]]:
    """Load and cache default attack config dictionaries keyed by technique key."""
    global _DEFAULT_ATTACK_CONFIG_CACHE
    if _DEFAULT_ATTACK_CONFIG_CACHE is not None:
        return _DEFAULT_ATTACK_CONFIG_CACHE

    try:
        from hackagent.attacks.techniques.advprefix.config import (
            DEFAULT_PREFIX_GENERATION_CONFIG,
        )
        from hackagent.attacks.techniques.autodan_turbo.config import (
            DEFAULT_AUTODAN_TURBO_CONFIG,
        )
        from hackagent.attacks.techniques.baseline.config import DEFAULT_TEMPLATE_CONFIG
        from hackagent.attacks.techniques.bon.config import DEFAULT_BON_CONFIG
        from hackagent.attacks.techniques.cipherchat.config import (
            DEFAULT_CIPHERCHAT_CONFIG,
        )
        from hackagent.attacks.techniques.flipattack.config import (
            DEFAULT_FLIPATTACK_CONFIG,
        )
        from hackagent.attacks.techniques.h4rm3l.config import DEFAULT_H4RM3L_CONFIG
        from hackagent.attacks.techniques.pair.config import DEFAULT_PAIR_CONFIG
        from hackagent.attacks.techniques.pap.config import DEFAULT_PAP_CONFIG
        from hackagent.attacks.techniques.tap.config import DEFAULT_TAP_CONFIG

        _DEFAULT_ATTACK_CONFIG_CACHE = {
            "advprefix": DEFAULT_PREFIX_GENERATION_CONFIG,
            "baseline": DEFAULT_TEMPLATE_CONFIG,
            "pair": DEFAULT_PAIR_CONFIG,
            "autodan_turbo": DEFAULT_AUTODAN_TURBO_CONFIG,
            "flipattack": DEFAULT_FLIPATTACK_CONFIG,
            "tap": DEFAULT_TAP_CONFIG,
            "bon": DEFAULT_BON_CONFIG,
            "h4rm3l": DEFAULT_H4RM3L_CONFIG,
            "pap": DEFAULT_PAP_CONFIG,
            "cipherchat": DEFAULT_CIPHERCHAT_CONFIG,
        }
    except Exception:
        _DEFAULT_ATTACK_CONFIG_CACHE = {}

    return _DEFAULT_ATTACK_CONFIG_CACHE


def _get_attack_default_config(technique_key: str) -> Dict[str, Any]:
    """Return a copy of the default config dict for a technique key."""
    cache = _load_attack_default_config_cache()
    config = cache.get(technique_key, {})
    return copy.deepcopy(config) if isinstance(config, dict) else {}


def _extract_llm_roles_from_default_config(
    default_config: Dict[str, Any],
) -> Dict[str, Dict[str, Any]]:
    """Extract top-level LLM role dicts from an attack default config."""
    roles: Dict[str, Dict[str, Any]] = {}
    for role, value in default_config.items():
        if role in _COMMON_STATIC_ROLES or role == "judges":
            continue
        if _looks_like_llm_role_config(value):
            roles[role] = value
    return roles


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

    AttacksTab #goals-container {
        height: auto;
    }

    AttacksTab #dataset-container {
        display: none;
        height: auto;
    }

    AttacksTab #strategy-config-container {
        height: auto;
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
        self._attack_config_overrides: Dict[str, Any] = copy.deepcopy(
            self.initial_data.get("attack_config_overrides", {})
        )
        self._agent_adapter_operational_config: Optional[Dict[str, Any]] = (
            copy.deepcopy(self.initial_data.get("agent_adapter_operational_config"))
        )
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
                yield Label("Endpoint API Key:")
                yield Input(
                    placeholder="Optional API key for endpoint adapter",
                    id="endpoint-api-key",
                    password=True,
                )
                yield Static("")

                # --- Input source: Goals vs Dataset (radio toggle) ---
                yield Static("[bold]Input Source[/bold]", classes="section-title")
                with RadioSet(id="input-source-radio"):
                    yield RadioButton("Goals", value=True, id="radio-goals")
                    yield RadioButton("Dataset", id="radio-dataset")
                yield Static("")

                # Goals container (visible by default)
                with Vertical(id="goals-container"):
                    yield Label("Goals (what you want the agent to do incorrectly):")
                    goals_area = TextArea("Return fake weather data", id="attack-goals")
                    goals_area.styles.height = 5
                    yield goals_area

                # Dataset container (hidden by default)
                with Vertical(id="dataset-container"):
                    yield Label("Dataset:")
                    dataset_choices = [(k, k) for k in sorted(_DATASET_PRESETS)]
                    yield Select(
                        dataset_choices, id="dataset-preset", value="harmbench"
                    )
                    yield Static("")
                    yield Label("Limit (max samples):")
                    yield Input(value="5", id="dataset-limit", placeholder="e.g. 5")
                    yield Static("")
                    yield Label("Shuffle:")
                    yield Switch(value=True, id="dataset-shuffle")
                    yield Static("")
                    yield Label("Seed:")
                    yield Input(value="42", id="dataset-seed", placeholder="e.g. 42")
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

                # --- Common / advanced attack config overrides ---
                yield Static(
                    "[bold]Advanced Attack Configuration[/bold]",
                    classes="section-title",
                )
                yield Static(
                    "[dim]Defaults are prefilled. You can run as-is or override per run.[/dim]"
                )

                with Collapsible(
                    title="Roles (Judge / Category Classifier)", collapsed=False
                ):
                    yield Label("Judge Identifier:")
                    yield Input(value="hackagent-judge", id="common-judge-id")
                    yield Label("Judge Endpoint:")
                    yield Input(
                        value="https://api.hackagent.dev/v1",
                        id="common-judge-endpoint",
                    )
                    yield Label("Judge API Key:")
                    yield Input(value="", id="common-judge-api-key", password=True)
                    yield Label("Judge Type:")
                    yield Input(value="harmbench", id="common-judge-type")

                    yield Label("Judge Agent Type:")
                    yield Input(value="OPENAI_SDK", id="common-judge-agent-type")
                    yield Label("Classifier Agent Type:")
                    yield Input(value="OLLAMA", id="common-classifier-agent-type")

                    yield Label("Category Classifier Identifier:")
                    yield Input(
                        value="gemma3:4b",
                        id="common-classifier-id",
                    )
                    yield Label("Category Classifier Endpoint:")
                    yield Input(
                        value="http://localhost:11434",
                        id="common-classifier-endpoint",
                    )
                    yield Label("Category Classifier API Key:")
                    yield Input(
                        value="",
                        id="common-classifier-api-key",
                        password=True,
                    )

                    yield Label("Judge Top P:")
                    yield Input(value="", id="common-judge-top-p")

                    yield Label("Classifier Max Tokens:")
                    yield Input(value="100", id="common-classifier-max-tokens")
                    yield Label("Classifier Temperature:")
                    yield Input(value="0.0", id="common-classifier-temperature")

                with Collapsible(title="Judge Evaluation", collapsed=True):
                    yield Label("Judge Batch Size:")
                    yield Input(value="1", id="common-judge-batch-size")
                    yield Label("Max Judge Tokens:")
                    yield Input(value="4096", id="common-max-tokens-eval")
                    yield Label("Judge Timeout (s):")
                    yield Input(value="120", id="common-judge-timeout")
                    yield Label("Judge Temperature:")
                    yield Input(value="0.0", id="common-judge-temperature")
                    yield Label("Max Judge Retries:")
                    yield Input(value="1", id="common-max-judge-retries")

                with Collapsible(title="Execution Controls", collapsed=True):
                    yield Label("Batch Size:")
                    yield Input(value="1", id="common-batch-size")
                    yield Label("Goal Batch Size:")
                    yield Input(value="1", id="common-goal-batch-size")
                    yield Label("Goal Batch Workers:")
                    yield Input(value="1", id="common-goal-batch-workers")
                    yield Label("Start Step:")
                    yield Input(value="1", id="common-start-step")
                yield Static("")

                # --- Dynamic config container (populated on strategy change) ---
                yield Static(
                    "[bold]Attack-Specific Configuration[/bold]",
                    classes="section-title",
                    id="strategy-config-title",
                )
                yield Static(
                    "[dim]These fields apply only to the selected attack strategy.[/dim]",
                    id="strategy-config-note",
                )
                yield Vertical(id="strategy-config-container")

                # --- Advanced toggle ---
                yield Checkbox(
                    "Show advanced configuration (all fields as text boxes)",
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

        if self.initial_data.get("auto_execute_attack", False):
            self.call_after_refresh(lambda: self._execute_attack(dry_run=False))

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

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        """Toggle between Goals and Dataset input panels."""
        if event.radio_set.id == "input-source-radio":
            goals_container = self.query_one("#goals-container")
            dataset_container = self.query_one("#dataset-container")
            if event.pressed.id == "radio-goals":
                goals_container.display = True
                dataset_container.display = False
            else:
                goals_container.display = False
                dataset_container.display = True

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

    @on(Checkbox.Changed, "#advanced-toggle")
    def _on_advanced_toggle(self, event: Checkbox.Changed) -> None:
        """Handle advanced-toggle changes reliably across Textual versions."""
        self._show_advanced = bool(event.value)
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

        # Keep internal state aligned with the current checkbox value.
        try:
            self._show_advanced = self.query_one("#advanced-toggle", Checkbox).value
        except Exception:
            pass

        self._current_spec = spec

        # Update description
        desc_widget = self.query_one("#strategy-description", Static)
        desc_widget.update(f"[dim]{_escape(spec.description)}[/dim]")

        title_widget = self.query_one("#strategy-config-title", Static)
        title_widget.update(
            f"[bold]Attack-Specific Configuration ({_escape(spec.display_name)})[/bold]"
        )

        # Remove old config widgets
        container = self.query_one("#strategy-config-container", Vertical)
        container.remove_children()
        rendered_fields = 0
        spec_fields = self._get_renderable_spec_fields(spec)

        try:
            # Group fields by section
            for section in spec.sections():
                fields = [
                    field
                    for field in spec_fields
                    if field.section == section
                    and (self._show_advanced or not field.advanced)
                ]
                if not fields:
                    continue

                section_widgets: List[Any] = []

                for cfg_field in fields:
                    widget_id = _field_widget_id(cfg_field)
                    # Label with optional tooltip
                    label_text = cfg_field.label
                    if cfg_field.required:
                        label_text += " *"
                    section_widgets.append(Label(label_text))

                    if cfg_field.description:
                        section_widgets.append(
                            Static(
                                f"[dim]{_escape(cfg_field.description)}[/dim]",
                                classes="field-description",
                            )
                        )

                    # Render the appropriate widget
                    widget = self._create_field_widget(cfg_field, widget_id)
                    section_widgets.append(widget)
                    rendered_fields += 1

                # Build collapsible with children upfront to avoid mount-order issues.
                collapsible = Collapsible(
                    *section_widgets, title=section, collapsed=False
                )
                container.mount(collapsible)
        except Exception as render_exc:
            container.mount(
                Static(
                    f"[bold red]Failed to render attack-specific configuration:[/bold red] {_escape(render_exc)}"
                )
            )

        if rendered_fields == 0:
            container.mount(
                Static(
                    "[yellow]No fields are visible for this strategy with current filters. Enable advanced configuration to view all fields.[/yellow]"
                )
            )

        # Clear validation errors
        self.query_one("#validation-errors", Static).update("")

    def _create_field_widget(self, cfg_field: ConfigField, widget_id: str) -> Any:
        """Create the appropriate Textual widget for a :class:`ConfigField`."""
        if self._show_advanced:
            # Advanced mode intentionally uses plain text boxes for all fields.
            default_str = ""
            if cfg_field.default is not None:
                if isinstance(cfg_field.default, bool):
                    default_str = "true" if cfg_field.default else "false"
                else:
                    default_str = str(cfg_field.default)

            placeholder = ""
            if cfg_field.field_type == FieldType.BOOLEAN:
                placeholder = "true / false"
            elif cfg_field.field_type == FieldType.CHOICE and cfg_field.choices:
                placeholder = ", ".join(str(choice[1]) for choice in cfg_field.choices)
            elif cfg_field.min_value is not None and cfg_field.max_value is not None:
                placeholder = f"{cfg_field.min_value} – {cfg_field.max_value}"
            elif cfg_field.field_type == FieldType.INTEGER:
                placeholder = "integer"
            elif cfg_field.field_type == FieldType.FLOAT:
                placeholder = "number"

            return Input(value=default_str, placeholder=placeholder, id=widget_id)

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
        for cfg_field in self._get_renderable_spec_fields(self._current_spec):
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
                elif cfg_field.field_type == FieldType.BOOLEAN:
                    if isinstance(raw, str):
                        lowered = raw.strip().lower()
                        if lowered in {"true", "1", "yes", "y", "on"}:
                            raw = True
                        elif lowered in {"false", "0", "no", "n", "off"}:
                            raw = False

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
        if isinstance(self._agent_adapter_operational_config, dict):
            endpoint_api_key = self._agent_adapter_operational_config.get("api_key")
            if endpoint_api_key:
                self.query_one("#endpoint-api-key", Input).value = str(endpoint_api_key)
        if "goals" in self.initial_data:
            self.query_one("#attack-goals", TextArea).text = self.initial_data["goals"]
        if "timeout" in self.initial_data:
            self.query_one("#timeout", Input).value = str(self.initial_data["timeout"])

        strategy_value = self.initial_data.get(
            "attack_type"
        ) or self._attack_config_overrides.get("attack_type")
        if strategy_value:
            strategy_select = self.query_one("#attack-strategy", Select)
            strategy_select.value = str(strategy_value)
            self._render_strategy_config(str(strategy_value))

        if self._attack_config_overrides:
            self._prefill_strategy_fields(self._attack_config_overrides)

            judge_api_key = self._attack_config_overrides.get("judge", {}).get(
                "api_key"
            )
            if judge_api_key:
                self.query_one("#common-judge-api-key", Input).value = str(
                    judge_api_key
                )

            classifier_api_key = self._attack_config_overrides.get(
                "category_classifier", {}
            ).get("api_key")
            if classifier_api_key:
                self.query_one("#common-classifier-api-key", Input).value = str(
                    classifier_api_key
                )

        goals_from_overrides = self._attack_config_overrides.get("goals")
        if isinstance(goals_from_overrides, list) and goals_from_overrides:
            self.query_one("#attack-goals", TextArea).text = str(
                goals_from_overrides[0]
            )

        # ── Prefill dataset vs goals toggle ──
        dataset_cfg = self._attack_config_overrides.get("dataset")
        if isinstance(dataset_cfg, dict) and dataset_cfg.get("preset"):
            self.query_one("#radio-dataset", RadioButton).value = True
            self.query_one("#goals-container").display = False
            self.query_one("#dataset-container").display = True
            self.query_one("#dataset-preset", Select).value = dataset_cfg["preset"]
            if "limit" in dataset_cfg:
                self.query_one("#dataset-limit", Input).value = str(
                    dataset_cfg["limit"]
                )
            if "shuffle" in dataset_cfg:
                self.query_one("#dataset-shuffle", Switch).value = bool(
                    dataset_cfg["shuffle"]
                )
            if "seed" in dataset_cfg:
                self.query_one("#dataset-seed", Input).value = str(dataset_cfg["seed"])

    @staticmethod
    def _flatten_dict(data: Dict[str, Any], prefix: str = "") -> Dict[str, Any]:
        """Flatten nested dict keys using dot notation."""
        flat: Dict[str, Any] = {}
        for key, value in data.items():
            dotted_key = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict):
                flat.update(AttacksTab._flatten_dict(value, dotted_key))
            else:
                flat[dotted_key] = value
        return flat

    def _prefill_strategy_fields(self, attack_config: Dict[str, Any]) -> None:
        """Pre-fill strategy-specific form fields from attack config overrides."""
        if not self._current_spec:
            return

        flat_overrides = self._flatten_dict(attack_config)
        advanced_keys = {
            field.key
            for field in self._get_renderable_spec_fields(self._current_spec)
            if field.advanced
        }

        if advanced_keys.intersection(flat_overrides.keys()):
            advanced_toggle = self.query_one("#advanced-toggle", Checkbox)
            advanced_toggle.value = True
            self._show_advanced = True
            self._render_strategy_config(self._current_spec.technique_key)

        for cfg_field in self._get_renderable_spec_fields(self._current_spec):
            if cfg_field.key not in flat_overrides:
                continue

            widget_id = _field_widget_id(cfg_field)
            try:
                widget = self.query_one(f"#{widget_id}")
            except Exception:
                continue

            value = flat_overrides[cfg_field.key]

            if isinstance(widget, Select):
                widget.value = value
            elif isinstance(widget, Switch):
                widget.value = bool(value)
            elif isinstance(widget, TextArea):
                widget.text = "" if value is None else str(value)
            elif isinstance(widget, Input):
                widget.value = "" if value is None else str(value)

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
        endpoint_api_key = self.query_one("#endpoint-api-key", Input).value.strip()
        strategy_raw = self.query_one("#attack-strategy", Select).value
        timeout = self.query_one("#timeout", Input).value

        # Detect which input source is active (Goals vs Dataset)
        using_dataset = self.query_one("#radio-dataset", RadioButton).value

        # ── Basic validation ──
        if not agent_name:
            return
        if isinstance(agent_type_raw, NoSelection) or not agent_type_raw:
            return
        if not endpoint:
            return
        if isinstance(strategy_raw, NoSelection) or not strategy_raw:
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
        attack_config: Dict[str, Any] = copy.deepcopy(self._attack_config_overrides)
        if not isinstance(attack_config, dict):
            attack_config = {}

        def _to_int(raw: str) -> Optional[int]:
            try:
                return int(raw.strip())
            except Exception:
                return None

        def _to_float(raw: str) -> Optional[float]:
            try:
                return float(raw.strip())
            except Exception:
                return None

        # Apply common role configs from TUI form (with defaults).
        judge_id = self.query_one("#common-judge-id", Input).value.strip()
        judge_endpoint = self.query_one("#common-judge-endpoint", Input).value.strip()
        judge_api_key = self.query_one("#common-judge-api-key", Input).value.strip()
        judge_type = self.query_one("#common-judge-type", Input).value.strip()
        judge_agent_type = self.query_one(
            "#common-judge-agent-type", Input
        ).value.strip()
        judge_top_p = _to_float(self.query_one("#common-judge-top-p", Input).value)

        classifier_id = self.query_one("#common-classifier-id", Input).value.strip()
        classifier_endpoint = self.query_one(
            "#common-classifier-endpoint", Input
        ).value.strip()
        classifier_api_key = self.query_one(
            "#common-classifier-api-key", Input
        ).value.strip()
        classifier_agent_type = self.query_one(
            "#common-classifier-agent-type", Input
        ).value.strip()
        classifier_max_tokens = _to_int(
            self.query_one("#common-classifier-max-tokens", Input).value
        )
        classifier_temperature = _to_float(
            self.query_one("#common-classifier-temperature", Input).value
        )

        batch_size_judge = _to_int(
            self.query_one("#common-judge-batch-size", Input).value
        )
        max_tokens_eval = _to_int(
            self.query_one("#common-max-tokens-eval", Input).value
        )
        judge_timeout = _to_int(self.query_one("#common-judge-timeout", Input).value)
        judge_temperature = _to_float(
            self.query_one("#common-judge-temperature", Input).value
        )
        max_judge_retries = _to_int(
            self.query_one("#common-max-judge-retries", Input).value
        )

        batch_size = _to_int(self.query_one("#common-batch-size", Input).value)
        goal_batch_size = _to_int(
            self.query_one("#common-goal-batch-size", Input).value
        )
        goal_batch_workers = _to_int(
            self.query_one("#common-goal-batch-workers", Input).value
        )
        start_step = _to_int(self.query_one("#common-start-step", Input).value)

        attack_config.setdefault("judge", {})
        attack_config.setdefault("category_classifier", {})

        if judge_id:
            attack_config["judge"]["identifier"] = judge_id
        if judge_endpoint:
            attack_config["judge"]["endpoint"] = judge_endpoint
        if judge_api_key:
            attack_config["judge"]["api_key"] = judge_api_key
        else:
            attack_config["judge"].pop("api_key", None)
        if judge_type:
            attack_config["judge"]["type"] = judge_type
        if judge_agent_type:
            attack_config["judge"]["agent_type"] = judge_agent_type
        if judge_top_p is not None:
            attack_config["judge"]["top_p"] = judge_top_p

        if classifier_id:
            attack_config["category_classifier"]["identifier"] = classifier_id
        if classifier_endpoint:
            attack_config["category_classifier"]["endpoint"] = classifier_endpoint
        if classifier_api_key:
            attack_config["category_classifier"]["api_key"] = classifier_api_key
        else:
            attack_config["category_classifier"].pop("api_key", None)
        if classifier_agent_type:
            attack_config["category_classifier"]["agent_type"] = classifier_agent_type
        if classifier_max_tokens is not None:
            attack_config["category_classifier"]["max_tokens"] = classifier_max_tokens
        if classifier_temperature is not None:
            attack_config["category_classifier"]["temperature"] = classifier_temperature

        if batch_size_judge is not None:
            attack_config["batch_size_judge"] = batch_size_judge
        if max_tokens_eval is not None:
            attack_config["max_tokens_eval"] = max_tokens_eval
        if judge_timeout is not None:
            attack_config["judge_timeout"] = judge_timeout
        if judge_temperature is not None:
            attack_config["judge_temperature"] = judge_temperature
        if max_judge_retries is not None:
            attack_config["max_judge_retries"] = max_judge_retries

        if batch_size is not None:
            attack_config["batch_size"] = batch_size
        if goal_batch_size is not None:
            attack_config["goal_batch_size"] = goal_batch_size
        if goal_batch_workers is not None:
            attack_config["goal_batch_workers"] = goal_batch_workers
        if start_step is not None:
            attack_config["start_step"] = start_step

        # Strategy-specific values override the common defaults above.
        self._deep_merge_dicts(attack_config, strategy_config)
        self._strip_empty_api_keys(attack_config)
        attack_config["attack_type"] = strategy

        adapter_operational_config = copy.deepcopy(
            self._agent_adapter_operational_config or {}
        )
        adapter_operational_config["name"] = agent_name
        adapter_operational_config["endpoint"] = endpoint
        if endpoint_api_key:
            adapter_operational_config["api_key"] = endpoint_api_key
        else:
            adapter_operational_config.pop("api_key", None)
        self._agent_adapter_operational_config = adapter_operational_config

        # ── Populate goals or dataset from form ──
        if using_dataset:
            dataset_preset_raw = self.query_one("#dataset-preset", Select).value
            if (
                isinstance(dataset_preset_raw, type(Select.BLANK))
                or not dataset_preset_raw
            ):
                return
            dataset_cfg: Dict[str, Any] = {"preset": str(dataset_preset_raw)}
            try:
                limit_val = int(self.query_one("#dataset-limit", Input).value)
                dataset_cfg["limit"] = limit_val
            except (ValueError, TypeError):
                pass
            dataset_cfg["shuffle"] = self.query_one("#dataset-shuffle", Switch).value
            try:
                seed_val = int(self.query_one("#dataset-seed", Input).value)
                dataset_cfg["seed"] = seed_val
            except (ValueError, TypeError):
                pass
            attack_config["dataset"] = dataset_cfg
            attack_config.pop("goals", None)
            goals = ""
        else:
            goals = self.query_one("#attack-goals", TextArea).text
            if goals:
                attack_config["goals"] = [goals]
            else:
                return

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
                adapter_operational_config=self._agent_adapter_operational_config,
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
            is_local = not self.cli_config.api_key
            storage_note = (
                "[dim]Results saved locally → ~/.local/share/hackagent/hackagent.db[/dim]"
                if is_local
                else "[dim]Results have been saved to the HackAgent platform.[/dim]"
            )
            self.app.call_from_thread(
                status_widget.update,
                f"""[bold green]✅ Attack Completed Successfully![/bold green]

[bold]Agent:[/bold] {_escape(agent_name)}
[bold]Duration:[/bold] {duration:.1f} seconds
[bold]Results Generated:[/bold] {result_count}

[green]Attack execution finished![/green]
[dim]Check the Results tab to view detailed attack results.[/dim]
{storage_note}""",
            )

        except Exception as e:
            is_local = not self.cli_config.api_key
            key_hint = (
                "[dim]Ensure the agent endpoint is accessible.[/dim]"
                if is_local
                else "[dim]Ensure the agent endpoint is accessible and API key is valid.[/dim]"
            )
            self.app.call_from_thread(progress_bar.update, progress=0)
            self.app.call_from_thread(
                status_widget.update,
                f"""[bold red]❌ Attack Failed[/bold red]

[bold]Agent:[/bold] {_escape(agent_name)}
[bold]Error:[/bold] {_escape(str(e))}

[red]Attack execution encountered an error.[/red]
[dim]Please check your configuration and try again.[/dim]
{key_hint}""",
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
        self.query_one("#endpoint-api-key", Input).value = ""
        self.query_one("#attack-goals", TextArea).text = "Return fake weather data"
        self.query_one("#timeout", Input).value = "300"

        # Reset input source to Goals
        self.query_one("#radio-goals", RadioButton).value = True
        self.query_one("#goals-container").display = True
        self.query_one("#dataset-container").display = False
        self.query_one("#dataset-preset", Select).value = "harmbench"
        self.query_one("#dataset-limit", Input).value = "5"
        self.query_one("#dataset-shuffle", Switch).value = True
        self.query_one("#dataset-seed", Input).value = "42"

        self.query_one("#common-judge-id", Input).value = "hackagent-judge"
        self.query_one(
            "#common-judge-endpoint", Input
        ).value = "https://api.hackagent.dev/v1"
        self.query_one("#common-judge-api-key", Input).value = ""
        self.query_one("#common-judge-type", Input).value = "harmbench"
        self.query_one("#common-judge-agent-type", Input).value = "OPENAI_SDK"
        self.query_one("#common-judge-top-p", Input).value = ""

        self.query_one("#common-classifier-id", Input).value = "gemma3:4b"
        self.query_one(
            "#common-classifier-endpoint", Input
        ).value = "http://localhost:11434"
        self.query_one("#common-classifier-api-key", Input).value = ""
        self.query_one("#common-classifier-agent-type", Input).value = "OLLAMA"
        self.query_one("#common-classifier-max-tokens", Input).value = "100"
        self.query_one("#common-classifier-temperature", Input).value = "0.0"

        self.query_one("#common-judge-batch-size", Input).value = "1"
        self.query_one("#common-max-tokens-eval", Input).value = "4096"
        self.query_one("#common-judge-timeout", Input).value = "120"
        self.query_one("#common-judge-temperature", Input).value = "0.0"
        self.query_one("#common-max-judge-retries", Input).value = "1"

        self.query_one("#common-batch-size", Input).value = "1"
        self.query_one("#common-goal-batch-size", Input).value = "1"
        self.query_one("#common-goal-batch-workers", Input).value = "1"
        self.query_one("#common-start-step", Input).value = "1"

        status_widget = self.query_one("#execution-status", Static)
        progress_bar = self.query_one("#attack-progress", ProgressBar)
        status_widget.update("[dim]Configure attack parameters and click Execute[/dim]")
        progress_bar.update(progress=0)
        self.query_one("#validation-errors", Static).update("")

    def refresh_data(self) -> None:
        """Refresh attacks data."""
        pass

    @staticmethod
    def _deep_merge_dicts(base: Dict[str, Any], updates: Dict[str, Any]) -> None:
        """Deep-merge updates into base in place."""
        for key, value in updates.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                AttacksTab._deep_merge_dicts(base[key], value)
            else:
                base[key] = value

    @staticmethod
    def _strip_empty_api_keys(config: Dict[str, Any]) -> None:
        """Remove empty api_key entries recursively from nested config dicts."""
        for key in list(config.keys()):
            value = config[key]
            if isinstance(value, dict):
                AttacksTab._strip_empty_api_keys(value)
            elif key == "api_key" and (value is None or str(value).strip() == ""):
                config.pop(key, None)

    @staticmethod
    def _get_renderable_spec_fields(spec: AttackConfigSpec) -> List[ConfigField]:
        """Augment strategy fields with per-role LLM routing fields."""
        fields = [copy.deepcopy(field) for field in spec.fields]

        # Force role routing combo fields to be visible in default view.
        for cfg_field in fields:
            if "." not in cfg_field.key:
                continue
            role, attribute = cfg_field.key.split(".", 1)
            if role in _COMMON_STATIC_ROLES:
                continue
            if attribute in _ROLE_COMBO_FIELDS:
                cfg_field.advanced = False

        existing_keys = {field.key for field in fields}

        role_anchor: Dict[str, tuple[int, ConfigField, str]] = {}
        for index, cfg_field in enumerate(fields):
            if "." not in cfg_field.key:
                continue

            role, attribute = cfg_field.key.split(".", 1)
            if role in _COMMON_STATIC_ROLES:
                continue

            current_anchor = role_anchor.get(role)
            if current_anchor is None:
                role_anchor[role] = (index, cfg_field, attribute)
                continue

            _, current_field, current_attr = current_anchor
            if current_field.advanced and not cfg_field.advanced:
                role_anchor[role] = (index, cfg_field, attribute)
            elif (
                not current_field.advanced
                and not cfg_field.advanced
                and attribute == "endpoint"
                and current_attr != "endpoint"
            ):
                role_anchor[role] = (index, cfg_field, attribute)

        default_role_configs = _extract_llm_roles_from_default_config(
            _get_attack_default_config(spec.technique_key)
        )

        for role in default_role_configs:
            if role in _COMMON_STATIC_ROLES or role == "judges":
                continue
            if role not in role_anchor:
                role_title = _humanize_role_name(role)
                role_anchor[role] = (
                    max(len(fields) - 1, 0),
                    ConfigField(
                        key=f"{role}.identifier",
                        label=f"{role_title} Identifier",
                        field_type=FieldType.STRING,
                        section=f"{role_title} LLM",
                        advanced=False,
                    ),
                    "identifier",
                )

        if not role_anchor and not default_role_configs:
            return fields

        insertions: Dict[int, List[ConfigField]] = {}
        combo_labels = {
            "identifier": "Identifier",
            "endpoint": "Endpoint",
            "api_key": "API Key",
            "agent_type": "Agent Type",
        }

        for role, (anchor_index, anchor_field, _anchor_attr) in role_anchor.items():
            role_title = _humanize_role_name(role)
            role_defaults = default_role_configs.get(role, {})

            for attribute in _ROLE_COMBO_FIELDS:
                key = f"{role}.{attribute}"
                if key in existing_keys:
                    continue

                insertions.setdefault(anchor_index, []).append(
                    ConfigField(
                        key=key,
                        label=f"{role_title} {combo_labels[attribute]}",
                        field_type=FieldType.STRING,
                        default=role_defaults.get(attribute),
                        description=(
                            f"Optional {combo_labels[attribute].lower()} for the {role_title} role."
                        ),
                        section=anchor_field.section,
                        advanced=False,
                    )
                )
                existing_keys.add(key)

        result: List[ConfigField] = []
        for index, cfg_field in enumerate(fields):
            result.append(cfg_field)
            result.extend(insertions.get(index, []))
        return result
