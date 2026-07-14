# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Attacks Tab

Execute and manage security attacks with dynamic, strategy-aware configuration.
"""

import copy
from typing import Any, Dict, List, Optional

from textual import events, on
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
    SelectionList,
    Static,
    Switch,
    TabbedContent,
    TabPane,
    TextArea,
)
from textual.widgets._select import NoSelection

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
# Shared agent-type choices reused by target agent and guardrail selects.
# =====================================================================
_AGENT_TYPE_CHOICES = [
    ("Google ADK", "google-adk"),
    ("Claude Code", "claude-code"),
    ("Web (live browser)", "web"),
    ("LiteLLM", "litellm"),
    ("LangChain", "langchain"),
    ("OpenAI SDK", "openai-sdk"),
    ("Ollama", "ollama"),
    ("MCP", "mcp"),
    ("A2A", "a2a"),
]

# Agent types that run locally and therefore have no endpoint URL. For these
# the endpoint field is legitimately empty and must not block execution.
_ENDPOINT_OPTIONAL_AGENT_TYPES = {"claude-code"}


def _default_campaign_attack_keys() -> List[str]:
    """Return the default hack_chain/attack-selection keys: the Jailbreak
    evaluation campaign's primary attacks (h4rm3l → TAP → PAIR), in
    campaign order, mirroring ``HackAgent.hack_chain``'s default. Filtered
    to techniques that actually have a registered TUI spec, and falling
    back to the first registered technique if the campaign isn't
    resolvable (e.g. specs were pruned in a downstream deployment).
    """
    try:
        from hackagent.risks.jailbreak import JAILBREAK_PROFILE

        available = get_all_attack_specs()
        keys = [
            rec.technique.strip().lower() for rec in JAILBREAK_PROFILE.primary_attacks
        ]
        keys = [key for key in keys if key in available]
        if keys:
            return keys
    except Exception:
        pass

    all_specs = get_all_attack_specs()
    return [next(iter(all_specs))] if all_specs else []


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

    /* Keep form labels readable regardless of hover/focus state. */
    AttacksTab Label {
        color: $text;
        text-style: bold;
    }

    AttacksTab Label:hover {
        color: $text;
    }

    AttacksTab Collapsible Label {
        color: $text;
        text-style: bold;
    }

    /* Keep Input Source radio labels visible in all states. */
    AttacksTab RadioButton {
        color: $text;
    }

    AttacksTab RadioButton > .toggle--label {
        color: $text;
    }

    AttacksTab RadioButton.-on > .toggle--label {
        color: #ffffff;
    }

    AttacksTab RadioButton:hover > .toggle--label,
    AttacksTab RadioButton:focus > .toggle--label {
        color: $text;
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

    AttacksTab #attack-strategies {
        height: auto;
        border: solid $primary;
    }

    AttacksTab #escalate-only-mitigated-help {
        color: $text-muted;
        margin-bottom: 1;
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
        self._reduced_tui_logs = bool(self.initial_data.get("reduced_tui_logs", False))
        self._show_advanced = False
        self._advanced_hover_preview = False
        self._advanced_focus_preview = False
        self._current_spec: Optional[AttackConfigSpec] = None
        # Multi-attack (hack_chain) support: values collected for a strategy
        # are cached here when the user switches to configure a different
        # one, so switching back and forth doesn't lose edits. The strategy
        # whose config form is currently rendered is tracked separately from
        # which strategies are actually selected to run.
        self._strategy_value_cache: Dict[str, Dict[str, Any]] = {}
        self._focused_strategy: Optional[str] = None
        # Last selection applied to the "Configuring" dropdown — lets
        # `_sync_configuring_options` skip redundant `set_options()` calls
        # (see that method's docstring for why this matters).
        self._configuring_options_keys: Optional[List[str]] = None

    def compose(self) -> ComposeResult:
        """Compose the attacks layout."""
        # Build strategy choices from the registry
        all_specs = get_all_attack_specs()
        strategy_choices: List[tuple] = [
            (spec.display_name, spec.technique_key) for spec in all_specs.values()
        ]
        campaign_keys = _default_campaign_attack_keys()
        default_strategy = (
            campaign_keys[0]
            if campaign_keys
            else (strategy_choices[0][1] if strategy_choices else "advprefix")
        )

        with Horizontal():
            # ── Left side: Attack configuration form ──
            with VerticalScroll(id="attack-form-container"):
                yield Static("[bold cyan]⚔️  Attack Configuration[/bold cyan]")
                yield Static("")

                # --- Before Guardrail (input filter, sits before the target) ---
                with Collapsible(title="Before Guardrail (optional)", collapsed=True):
                    yield Static(
                        "[dim]Checks prompts before they reach the target model.[/dim]"
                    )
                    yield Label("Agent Name:")
                    yield Input(
                        placeholder="e.g., gpt-oss-safeguard-20b",
                        id="before-gr-name",
                    )
                    yield Label("Agent Type:")
                    yield Select(
                        _AGENT_TYPE_CHOICES,
                        id="before-gr-type",
                        value="google-adk",
                    )
                    yield Label("Endpoint URL:")
                    yield Input(
                        placeholder="e.g., http://localhost:8000",
                        id="before-gr-endpoint",
                    )
                yield Static("")
                # --- Agent settings (always shown) ---
                with Collapsible(title="Target Agent", collapsed=False):
                    yield Label("Agent Name:")
                    yield Input(placeholder="e.g., weather-bot", id="agent-name")
                    yield Static("")

                    yield Label("Agent Type:")
                    yield Select(
                        _AGENT_TYPE_CHOICES,
                        id="agent-type",
                        value="google-adk",
                    )
                    yield Static("")

                    yield Label("Endpoint URL:")
                    yield Input(
                        placeholder="e.g., http://localhost:8000", id="endpoint-url"
                    )
                yield Static("")
                # --- After Guardrail (output filter, sits after the target) ---
                with Collapsible(title="After Guardrail (optional)", collapsed=True):
                    yield Static(
                        "[dim]Checks responses after the target model generates them.[/dim]"
                    )
                    yield Label("Agent Name:")
                    yield Input(
                        placeholder="e.g., gpt-oss-safeguard-20b",
                        id="after-gr-name",
                    )
                    yield Label("Agent Type:")
                    yield Select(
                        _AGENT_TYPE_CHOICES,
                        id="after-gr-type",
                        value="google-adk",
                    )
                    yield Label("Endpoint URL:")
                    yield Input(
                        placeholder="e.g., http://localhost:8000",
                        id="after-gr-endpoint",
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
                # A SelectionList (not a single Select) so users can pick more
                # than one attack. Selection *order* becomes the chain order:
                # when 2+ are selected, Execute runs `HackAgent.hack_chain`
                # instead of `HackAgent.hack`, escalating each goal through
                # the selected attacks in the order they were checked.
                #
                # Nothing is pre-selected here via the option tuples: doing
                # so would select in *option list* order (registration
                # order in attack_specs.py), not the desired campaign order
                # (h4rm3l → TAP → PAIR). `on_mount` selects the default
                # campaign attacks explicitly, in the right order, instead.
                yield Static("[bold]Attack Strategy[/bold]", classes="section-title")
                yield Static(
                    "[dim]Select one attack, or check multiple to chain them "
                    "Check order sets the chain order. Defaults to the Jailbreak "
                    "evaluation campaign (h4rm3l → TAP → PAIR).[/dim]"
                )
                yield SelectionList(*strategy_choices, id="attack-strategies")
                yield Static("")

                yield Checkbox(
                    "Escalate only mitigated goals to the next attack",
                    id="escalate-only-mitigated",
                    value=False,
                )
                yield Static(
                    "[dim]Chain mode (2+ attacks checked): a goal moves to "
                    "the next attack only if the previous one mitigated it; "
                    "goals that already succeeded are dropped. Uncheck to "
                    "instead run every checked attack against every goal.[/dim]",
                    id="escalate-only-mitigated-help",
                )
                yield Static("")

                yield Label("Configuring:")
                yield Select(
                    strategy_choices,
                    id="attack-strategy-focus",
                    value=default_strategy,
                )
                yield Static("", id="strategy-description")
                yield Static("")

                # --- Dynamic config container (populated on strategy change) ---
                yield Vertical(id="strategy-config-container")

                # --- Advanced toggle ---
                yield Checkbox(
                    "Show advanced configuration (all fields as text boxes)",
                    id="advanced-toggle",
                    value=False,
                    classes="advanced-toggle",
                )
                yield Static(
                    "[dim]Hover or focus this option to preview all advanced settings. "
                    "Check it to keep them always visible.[/dim]"
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
        # Default to the Jailbreak evaluation campaign's primary attacks
        # (h4rm3l → TAP → PAIR), matching HackAgent.hack_chain's default,
        # so Execute runs a chain out of the box. `_prefill_form()` below
        # overrides this with a single explicit attack when re-running one
        # specific attack (e.g. from the Results tab).
        self._select_default_campaign_attacks()

        if self.initial_data:
            self._prefill_form()

        self.call_after_refresh(self._add_initial_messages)

        if self.initial_data.get("auto_execute_attack", False):
            self.call_after_refresh(lambda: self._execute_attack(dry_run=False))

    def _select_default_campaign_attacks(self) -> None:
        """Select the default hack_chain attack set (the Jailbreak
        evaluation campaign's primary attacks, in campaign order) and
        render/focus the first one's config form."""
        keys = _default_campaign_attack_keys()
        if not keys:
            return

        strategies = self.query_one("#attack-strategies", SelectionList)
        strategies.deselect_all()
        for key in keys:
            strategies.select(key)

        self._sync_configuring_options(keys)
        self._sync_chain_mode_visibility(keys)

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
        """React to the 'Configuring' strategy selector changes."""
        if event.select.id == "attack-strategy-focus":
            value = event.value
            if value and not isinstance(value, NoSelection):
                self._switch_focused_strategy(str(value))

    def on_selection_list_selected_changed(
        self, event: SelectionList.SelectedChanged
    ) -> None:
        """React to attack multi-selection changes (which attacks will run)."""
        if event.selection_list.id != "attack-strategies":
            return
        selected = list(event.selection_list.selected)
        self._sync_configuring_options(selected)
        self._sync_chain_mode_visibility(selected)

    def _sync_configuring_options(self, selected: List[str]) -> None:
        """Restrict the 'Configuring' dropdown to only the checked attacks,
        in check order, so the config form can't be opened for a strategy
        that isn't actually part of the current run.

        A no-op if *selected* is unchanged since the last call — a single
        bulk selection change (e.g. selecting the N default campaign
        attacks in a loop) posts one ``SelectedChanged`` message *per*
        ``.select()`` call rather than one combined message, so this method
        can be invoked several times in a row for what is conceptually one
        update; skipping true no-ops avoids redundantly rebuilding the
        dropdown's options each time.
        """
        if selected == self._configuring_options_keys:
            return
        self._configuring_options_keys = list(selected)

        all_specs = get_all_attack_specs()
        focus_choices = [
            (all_specs[key].display_name, key) for key in selected if key in all_specs
        ]
        focus_select = self.query_one("#attack-strategy-focus", Select)

        if not focus_choices:
            # Nothing checked — leave the dropdown empty; execute-time
            # validation already rejects an empty selection.
            focus_select.set_options([])
            return

        focus_select.set_options(focus_choices)
        new_focus = (
            self._focused_strategy
            if self._focused_strategy in selected
            else selected[0]
        )
        focus_select.value = new_focus
        if new_focus != self._focused_strategy:
            self._switch_focused_strategy(new_focus)

    def _sync_chain_mode_visibility(self, selected: Optional[List[str]] = None) -> None:
        """Show the hack_chain escalation toggle only when 2+ attacks are checked."""
        if selected is None:
            try:
                selected = list(
                    self.query_one("#attack-strategies", SelectionList).selected
                )
            except Exception:
                selected = []
        is_chain = len(selected) > 1
        try:
            self.query_one("#escalate-only-mitigated", Checkbox).display = is_chain
            self.query_one("#escalate-only-mitigated-help", Static).display = is_chain
        except Exception:
            pass

    def _switch_focused_strategy(self, technique_key: str) -> None:
        """Switch which strategy's config form is displayed.

        Caches the currently-displayed strategy's field values first (so
        switching back to it later, e.g. after adding it to the chain
        selection, restores prior edits instead of resetting to defaults),
        then renders *technique_key*'s form, prefilling it from the cache if
        it was previously configured in this session.

        A no-op if *technique_key* is already focused and rendered — avoids
        redundantly rebuilding the same config form (e.g. when the
        "Configuring" Select's own internal blank-reset-then-restore cycle
        during ``set_options()`` briefly reports the previous value again).
        """
        if technique_key == self._focused_strategy and self._current_spec is not None:
            return
        if self._focused_strategy and self._focused_strategy != technique_key:
            self._strategy_value_cache[self._focused_strategy] = (
                self._collect_strategy_config()
            )
        self._focused_strategy = technique_key
        self._render_strategy_config(technique_key)
        cached = self._strategy_value_cache.get(technique_key)
        if cached and self._current_spec:
            self._apply_values_to_spec_widgets(self._current_spec, cached)

    def _apply_values_to_spec_widgets(
        self, spec: AttackConfigSpec, flat_values: Dict[str, Any]
    ) -> None:
        """Write *flat_values* (dotted-key -> value) into the mounted widgets
        for *spec*'s fields, skipping any field without a mounted widget
        (e.g. an advanced field while advanced mode is off)."""
        for cfg_field in spec.fields:
            if cfg_field.key not in flat_values:
                continue
            widget_id = _field_widget_id(cfg_field)
            try:
                widget = self.query_one(f"#{widget_id}")
            except Exception:
                continue
            value = flat_values[cfg_field.key]
            if isinstance(widget, Select):
                widget.value = value
            elif isinstance(widget, Switch):
                widget.value = bool(value)
            elif isinstance(widget, TextArea):
                widget.text = "" if value is None else str(value)
            elif isinstance(widget, Input):
                widget.value = "" if value is None else str(value)

    def _resolve_config_for_strategy(self, technique_key: str) -> Dict[str, Any]:
        """Return the flat (dotted-key) config values for *technique_key*.

        If it is the strategy currently displayed in the form, values are
        read live from the widgets (picking up not-yet-cached edits).
        Otherwise, the cached values from the last time it was configured
        are used, falling back to the spec's defaults if it was never
        opened in this session.
        """
        spec = get_attack_config_spec(technique_key)
        if spec is None:
            return {}
        if technique_key == self._focused_strategy and self._current_spec is spec:
            return self._collect_strategy_config()
        cached = self._strategy_value_cache.get(technique_key)
        if cached is not None:
            return cached
        return spec.defaults_dict()

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        """React to the advanced toggle."""
        if event.checkbox.id == "advanced-toggle":
            self._sync_advanced_visibility()

    @on(Checkbox.Changed, "#advanced-toggle")
    def _on_advanced_toggle(self, event: Checkbox.Changed) -> None:
        """Handle advanced-toggle changes reliably across Textual versions."""
        self._sync_advanced_visibility()

    @on(events.Enter, "#advanced-toggle")
    def _on_advanced_toggle_hover_enter(self, _: events.Enter) -> None:
        """Preview advanced settings while hovering the advanced-toggle control."""
        self._advanced_hover_preview = True
        self._sync_advanced_visibility()

    @on(events.Leave, "#advanced-toggle")
    def _on_advanced_toggle_hover_leave(self, _: events.Leave) -> None:
        """Hide hover-based advanced settings preview when pointer leaves control."""
        self._advanced_hover_preview = False
        self._sync_advanced_visibility()

    def on_focus(self, _: events.Focus) -> None:
        """Preview advanced settings when keyboard focus reaches advanced-toggle."""
        focused = self.app.focused
        self._advanced_focus_preview = bool(
            focused is not None and getattr(focused, "id", None) == "advanced-toggle"
        )
        self._sync_advanced_visibility()

    def on_blur(self, _: events.Blur) -> None:
        """Hide focus-based preview once advanced-toggle is no longer focused."""
        focused = self.app.focused
        self._advanced_focus_preview = bool(
            focused is not None and getattr(focused, "id", None) == "advanced-toggle"
        )
        self._sync_advanced_visibility()

    def _sync_advanced_visibility(self) -> None:
        """Recompute advanced visibility from toggle state and hover preview state."""
        try:
            pinned = bool(self.query_one("#advanced-toggle", Checkbox).value)
        except Exception:
            pinned = self._show_advanced

        should_show = (
            pinned or self._advanced_hover_preview or self._advanced_focus_preview
        )
        if self._show_advanced == should_show:
            return

        self._show_advanced = should_show
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
            pinned = bool(self.query_one("#advanced-toggle", Checkbox).value)
            self._show_advanced = (
                pinned or self._advanced_hover_preview or self._advanced_focus_preview
            )
        except Exception:
            pass

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

            # Build collapsible with children upfront to avoid mount-order issues.
            collapsible = Collapsible(*section_widgets, title=section, collapsed=False)
            container.mount(collapsible)

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
                if isinstance(raw, NoSelection):
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
            agent_type_value = self.initial_data["agent_type"]
            # Only set known choices — an unrecognised value would raise
            # InvalidSelectValueError and crash the tab on mount.
            valid_types = {value for _, value in _AGENT_TYPE_CHOICES}
            if agent_type_value in valid_types:
                self.query_one("#agent-type", Select).value = agent_type_value
        if "endpoint" in self.initial_data:
            self.query_one("#endpoint-url", Input).value = self.initial_data["endpoint"]
        if "goals" in self.initial_data:
            self.query_one("#attack-goals", TextArea).text = self.initial_data["goals"]
        if "timeout" in self.initial_data:
            self.query_one("#timeout", Input).value = str(self.initial_data["timeout"])

        strategy_value = self.initial_data.get(
            "attack_type"
        ) or self._attack_config_overrides.get("attack_type")
        if strategy_value:
            strategy_value = str(strategy_value)
            strategies = self.query_one("#attack-strategies", SelectionList)
            strategies.deselect_all()
            strategies.select(strategy_value)

            def _finish_strategy_prefill(key: str = strategy_value) -> None:
                # Deferred for the same reason as
                # `_select_default_campaign_attacks`: let the queued
                # `SelectedChanged` messages from the calls above drain
                # before touching the "Configuring" dropdown. Field-value
                # prefill runs in the same deferred step, after it, so
                # `_current_spec` reflects `key` by the time it runs.
                self._sync_configuring_options([key])
                self._sync_chain_mode_visibility([key])
                if self._attack_config_overrides:
                    self._prefill_strategy_fields(self._attack_config_overrides)

            self.call_after_refresh(_finish_strategy_prefill)
        elif self._attack_config_overrides:
            self._prefill_strategy_fields(self._attack_config_overrides)

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
            field.key for field in self._current_spec.fields if field.advanced
        }

        if advanced_keys.intersection(flat_overrides.keys()):
            advanced_toggle = self.query_one("#advanced-toggle", Checkbox)
            advanced_toggle.value = True
            self._show_advanced = True
            self._render_strategy_config(self._current_spec.technique_key)

        for cfg_field in self._current_spec.fields:
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
        """Execute the configured attack (or attack chain).

        Args:
            dry_run: Whether to run in dry-run mode
        """
        agent_name = self.query_one("#agent-name", Input).value
        agent_type_raw = self.query_one("#agent-type", Select).value
        endpoint = self.query_one("#endpoint-url", Input).value
        timeout = self.query_one("#timeout", Input).value

        selected_strategies = [
            str(v) for v in self.query_one("#attack-strategies", SelectionList).selected
        ]

        # Detect which input source is active (Goals vs Dataset)
        using_dataset = self.query_one("#radio-dataset", RadioButton).value

        # ── Basic validation ──
        # Surface why nothing happened instead of returning silently, otherwise
        # the Execute button looks dead (e.g. the claude-code preset, which has
        # no endpoint, used to be rejected by the blanket endpoint check).
        errors_widget = self.query_one("#validation-errors", Static)

        def _reject(message: str) -> None:
            errors_widget.update(f"[bold red]{message}[/bold red]")

        agent_type = (
            "" if isinstance(agent_type_raw, NoSelection) else str(agent_type_raw)
        )

        if not agent_name:
            _reject("Agent name is required.")
            return
        if not agent_type:
            _reject("Select an agent type.")
            return
        # Endpoint is required for everything except local agent types.
        if not endpoint and agent_type not in _ENDPOINT_OPTIONAL_AGENT_TYPES:
            _reject("Endpoint URL is required for this agent type.")
            return
        if not selected_strategies:
            _reject("Check at least one attack strategy.")
            return
        try:
            timeout_int = int(timeout)
            if timeout_int <= 0:
                _reject("Timeout must be a positive integer.")
                return
        except ValueError:
            _reject("Timeout must be a positive integer.")
            return

        is_chain = len(selected_strategies) > 1
        strategy_label = " → ".join(selected_strategies)

        # ── Collect & validate config for every selected strategy ──
        for technique_key in selected_strategies:
            spec = get_attack_config_spec(technique_key)
            if spec is None:
                continue
            resolved = self._resolve_config_for_strategy(technique_key)
            errors = spec.validate(resolved)
            if errors:
                errors_widget.update(
                    f"[bold red]Validation errors ({spec.display_name}):[/bold red]\n"
                    + "\n".join(f"  • {e}" for e in errors)
                )
                return

        errors_widget.update("")  # clear previous errors

        # Build one attack_config dict per selected strategy (nested).
        per_strategy_attack_config: Dict[str, Dict[str, Any]] = {}
        for technique_key in selected_strategies:
            flat_values = self._resolve_config_for_strategy(technique_key)
            expanded = self._expand_dotted_keys(flat_values)
            step_config: Dict[str, Any] = copy.deepcopy(self._attack_config_overrides)
            if not isinstance(step_config, dict):
                step_config = {}
            self._deep_merge_dicts(step_config, expanded)
            step_config["attack_type"] = technique_key
            per_strategy_attack_config[technique_key] = step_config

        # ── Populate goals or dataset from form ──
        attack_config: Optional[Dict[str, Any]] = None
        attacks_list: Optional[List[Dict[str, Any]]] = None
        chain_goals: Optional[List[str]] = None

        if is_chain:
            attacks_list = [
                per_strategy_attack_config[key] for key in selected_strategies
            ]
            # Only the first step needs a goal source — hack_chain forwards
            # the surviving goals from each step to the next one itself.
            for step_config in attacks_list[1:]:
                step_config.pop("goals", None)
                step_config.pop("dataset", None)
                step_config.pop("intents", None)

            if using_dataset:
                dataset_preset_raw = self.query_one("#dataset-preset", Select).value
                if (
                    isinstance(dataset_preset_raw, NoSelection)
                    or not dataset_preset_raw
                ):
                    _reject("Select a dataset preset.")
                    return
                dataset_cfg: Dict[str, Any] = {"preset": str(dataset_preset_raw)}
                try:
                    limit_val = int(self.query_one("#dataset-limit", Input).value)
                    dataset_cfg["limit"] = limit_val
                except (ValueError, TypeError):
                    pass
                dataset_cfg["shuffle"] = self.query_one(
                    "#dataset-shuffle", Switch
                ).value
                try:
                    seed_val = int(self.query_one("#dataset-seed", Input).value)
                    dataset_cfg["seed"] = seed_val
                except (ValueError, TypeError):
                    pass
                attacks_list[0]["dataset"] = dataset_cfg
                attacks_list[0].pop("goals", None)
                goals = ""
            else:
                goals = self.query_one("#attack-goals", TextArea).text
                if goals:
                    chain_goals = [goals]
                else:
                    _reject("Enter at least one attack goal, or switch to a dataset.")
                    return
        else:
            attack_config = per_strategy_attack_config[selected_strategies[0]]
            if using_dataset:
                dataset_preset_raw = self.query_one("#dataset-preset", Select).value
                if (
                    isinstance(dataset_preset_raw, NoSelection)
                    or not dataset_preset_raw
                ):
                    _reject("Select a dataset preset.")
                    return
                dataset_cfg = {"preset": str(dataset_preset_raw)}
                try:
                    limit_val = int(self.query_one("#dataset-limit", Input).value)
                    dataset_cfg["limit"] = limit_val
                except (ValueError, TypeError):
                    pass
                dataset_cfg["shuffle"] = self.query_one(
                    "#dataset-shuffle", Switch
                ).value
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
                    _reject("Enter at least one attack goal, or switch to a dataset.")
                    return

        escalate_only_mitigated = True
        if is_chain:
            escalate_only_mitigated = self.query_one(
                "#escalate-only-mitigated", Checkbox
            ).value

        status_widget = self.query_one("#execution-status", Static)
        progress_bar = self.query_one("#attack-progress", ProgressBar)

        if dry_run:
            # Pretty-print the full config for review
            import json

            config_preview = json.dumps(
                attacks_list if is_chain else attack_config, indent=2, default=str
            )
            chain_note = (
                f"\n[bold]Escalate Only Mitigated:[/bold] {escalate_only_mitigated}"
                if is_chain
                else ""
            )
            status_widget.update(
                f"""[bold yellow]Dry Run Mode[/bold yellow]

[bold]Agent:[/bold] {_escape(agent_name)}
[bold]Type:[/bold] {_escape(agent_type)}
[bold]Endpoint:[/bold] {_escape(endpoint)}
[bold]Strategy:[/bold] {_escape(strategy_label)}
[bold]Goals:[/bold] {_escape(goals)}
[bold]Timeout:[/bold] {timeout}s{chain_note}

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
[bold]Strategy:[/bold] {_escape(strategy_label)}
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
                        attacks=attacks_list,
                        chain_goals=chain_goals,
                        escalate_only_mitigated=escalate_only_mitigated,
                        strategy_label=strategy_label,
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
        attack_config: Optional[Dict[str, Any]],
        attacks: Optional[List[Dict[str, Any]]] = None,
        chain_goals: Optional[List[str]] = None,
        escalate_only_mitigated: bool = True,
        strategy_label: str = "",
    ) -> None:
        """Run attack (or attack chain) in background thread with progress updates.

        Args:
            agent_name: Name of the target agent
            agent_type: Type of agent (google-adk, litellm, etc.)
            endpoint: Agent endpoint URL
            goals: Attack goals
            timeout: Timeout in seconds
            attack_config: Full attack configuration dict for a single attack
                (already built). ``None`` when running a chain — use
                ``attacks`` instead.
            attacks: Ordered list of per-step attack_config dicts. When
                provided (2+ strategies checked), ``HackAgent.hack_chain`` is
                used instead of ``HackAgent.hack``.
            chain_goals: Explicit goal list forwarded to ``hack_chain`` (goals
                entered as free text). ``None`` when goals are sourced from a
                dataset set on ``attacks[0]``.
            escalate_only_mitigated: Forwarded to ``hack_chain`` — whether a
                goal only advances to the next attack if mitigated.
            strategy_label: Human-readable strategy name(s) for status text.
        """
        import io
        import logging
        import os
        import re
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
        if self._reduced_tui_logs:
            self.app.call_from_thread(
                log_viewer.add_log,
                "Reduced logs mode enabled: prompt/payload content is hidden.",
                "INFO",
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

        def _sanitize_log_message(message: str) -> Optional[str]:
            """Hide prompt/request payload details while preserving operational logs."""
            if not self._reduced_tui_logs:
                return message

            sanitized = message

            # Redact direct prompt previews while preserving structural info.
            sanitized = re.sub(
                r"(with\s+\d+\s+messages:\s+)(.+)$",
                r"\1<redacted>",
                sanitized,
                flags=re.IGNORECASE,
            )
            sanitized = re.sub(
                r"(with\s+prompt:\s+)(.+)$",
                r"\1<redacted>",
                sanitized,
                flags=re.IGNORECASE,
            )

            lowered = sanitized.lower()
            # Drop log lines that are mostly raw request/response payload dumps.
            sensitive_markers = (
                "message preview:",
                "payload:",
                "messages=[",
                "request payload",
                "response payload",
            )
            if any(marker in lowered for marker in sensitive_markers):
                return None

            return sanitized

        def _filtered_log_callback(message: str, level: str) -> None:
            sanitized = _sanitize_log_message(message)
            if sanitized is None:
                return
            log_viewer.add_log(sanitized, level)

        tui_log_level = logging.INFO
        tui_log_handler = TUILogHandler(
            app=self.app,
            callback=_filtered_log_callback,
            level=tui_log_level,
        )
        hackagent_logger.addHandler(tui_log_handler)
        hackagent_logger.setLevel(tui_log_level)

        # Build the structured event bus and hook the actions viewer.
        # The bus is also passed to ``agent.hack(...)`` below so trackers
        # emit goal/step/trace events as the attack runs.
        from hackagent.cli.tui.events import TUIEventBus

        tui_event_bus = TUIEventBus()
        actions_viewer.subscribe_to_bus(tui_event_bus, self.app)

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

            # Build guardrail configs from form fields
            before_gr_name = self.query_one("#before-gr-name", Input).value.strip()
            after_gr_name = self.query_one("#after-gr-name", Input).value.strip()

            before_guardrail = None
            if before_gr_name:
                before_gr_type_raw = self.query_one("#before-gr-type", Select).value
                before_gr_endpoint = self.query_one(
                    "#before-gr-endpoint", Input
                ).value.strip()
                before_guardrail = {
                    "identifier": before_gr_name.capitalize,
                    "agent_type": str(before_gr_type_raw),
                    "endpoint": before_gr_endpoint,
                }

            after_guardrail = None
            if after_gr_name:
                after_gr_type_raw = self.query_one("#after-gr-type", Select).value
                after_gr_endpoint = self.query_one(
                    "#after-gr-endpoint", Input
                ).value.strip()
                after_guardrail = {
                    "identifier": after_gr_name,
                    "agent_type": str(after_gr_type_raw),
                    "endpoint": after_gr_endpoint,
                }

            agent = HackAgent(
                name=agent_name,
                endpoint=endpoint,
                agent_type=agent_type_enum,
                timeout=5.0,
                adapter_operational_config=self._agent_adapter_operational_config,
                before_guardrail=before_guardrail,
                after_guardrail=after_guardrail,
            )

            self.app.call_from_thread(progress_bar.update, progress=30)

            strategy_name = strategy_label or (
                attack_config.get("attack_type", "unknown")
                if attack_config
                else "unknown"
            )
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

            # Event-driven progress: each `goal_finalized` advances the bar
            # toward 95% based on the expected goal count carried by the
            # orchestrator's `step_started` event. Anything beyond execution
            # (sync to backend) takes the final 5%.
            progress_state = {"goals_done": 0, "expected": 0}

            def _on_bus_event(event: Any) -> None:
                et = event.event_type
                payload = event.payload or {}

                if (
                    et == "step_started"
                    and payload.get("step_name") == "Attack Execution"
                ):
                    expected = payload.get("expected_total_goals") or 0
                    progress_state["expected"] = int(expected) if expected else 0
                    self.app.call_from_thread(progress_bar.update, progress=45)
                    self.app.call_from_thread(
                        status_widget.update,
                        f"""[bold cyan]⚔️ Executing {_escape(strategy_name)} Attack...[/bold cyan]

[bold]Goals to process:[/bold] {progress_state["expected"] or "unknown"}

[yellow]⏳ Attack running...[/yellow]
[dim]Progress: 45%[/dim]""",
                    )
                    return

                if et == "goal_finalized":
                    progress_state["goals_done"] += 1
                    expected = progress_state["expected"]
                    if expected > 0:
                        pct = 45 + int(50 * progress_state["goals_done"] / expected)
                        pct = min(pct, 95)
                    else:
                        # Unknown total — creep up but never reach 95%
                        pct = min(45 + progress_state["goals_done"] * 5, 90)
                    self.app.call_from_thread(progress_bar.update, progress=pct)
                    success = bool(payload.get("success"))
                    icon = "✓" if success else "✗"
                    elapsed = payload.get("elapsed_s")
                    elapsed_s = (
                        f" ({elapsed:.1f}s)"
                        if isinstance(elapsed, (int, float))
                        else ""
                    )
                    summary = (
                        f"Goal {progress_state['goals_done']}"
                        + (f"/{expected}" if expected else "")
                        + f"  {icon}{elapsed_s}"
                    )
                    self.app.call_from_thread(
                        status_widget.update,
                        f"""[bold cyan]⚔️ Executing {_escape(strategy_name)} Attack...[/bold cyan]

[bold]Last:[/bold] {summary}

[yellow]⏳ Attack running...[/yellow]
[dim]Progress: {pct}%[/dim]""",
                    )
                    return

                if (
                    et == "step_started"
                    and payload.get("step_name") == "Evaluation Pipeline"
                ):
                    self.app.call_from_thread(progress_bar.update, progress=96)
                    self.app.call_from_thread(
                        status_widget.update,
                        """[bold cyan]⚖ Running evaluation pipeline...[/bold cyan]

[dim]Progress: 96%[/dim]""",
                    )

            tui_event_bus.subscribe(_on_bus_event)

            try:
                if attacks is not None:
                    results = agent.hack_chain(
                        attacks=attacks,
                        goals=chain_goals,
                        run_config_override={"timeout": timeout},
                        fail_on_run_error=True,
                        escalate_only_mitigated=escalate_only_mitigated,
                        _tui_event_bus=tui_event_bus,
                    )
                else:
                    results = agent.hack(
                        attack_config=attack_config,
                        run_config_override={"timeout": timeout},
                        fail_on_run_error=True,
                        _tui_event_bus=tui_event_bus,
                    )
            finally:
                tui_event_bus.unsubscribe(_on_bus_event)
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
            storage_note = "[dim]Results saved locally → ~/.local/share/hackagent/hackagent.db[/dim]"
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
            key_hint = "[dim]Ensure the agent endpoint is accessible.[/dim]"
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

        # Reset strategy selection back to the default evaluation campaign.
        self.query_one("#escalate-only-mitigated", Checkbox).value = True
        self._select_default_campaign_attacks()

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
