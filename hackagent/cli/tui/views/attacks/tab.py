# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""The ``AttacksTab`` widget: layout wiring, lifecycle and event handlers."""

import copy
from typing import Any, Dict, List, Optional

from textual import events, on
from textual.binding import Binding
from textual.containers import Container
from textual.widgets import (
    Button,
    Checkbox,
    Input,
    ProgressBar,
    RadioButton,
    RadioSet,
    RichLog,
    Select,
    SelectionList,
    Static,
    Switch,
    TextArea,
)
from textual.widgets._select import NoSelection


from hackagent.cli.config import CLIConfig
from hackagent.cli.tui.attack_specs import (
    AttackConfigSpec,
)
from hackagent.cli.tui.widgets.actions import AgentActionsViewer
from hackagent.cli.tui.widgets.logs import AttackLogViewer


from hackagent.cli.tui.views.attacks.helpers import (
    _default_campaign_attack_keys,
)

from hackagent.cli.tui.views.attacks.executor import AttacksExecutorMixin
from hackagent.cli.tui.views.attacks.form import AttacksFormMixin
from hackagent.cli.tui.views.attacks.layout import AttacksLayoutMixin
from hackagent.cli.tui.views.attacks.runner import AttacksRunnerMixin


class AttacksTab(
    AttacksLayoutMixin,
    AttacksFormMixin,
    AttacksRunnerMixin,
    AttacksExecutorMixin,
    Container,
):
    """Execute and manage security attacks with strategy-aware configuration."""

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
        color: $brand-text;
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
