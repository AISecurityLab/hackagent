# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""The ``AttacksTab`` widget: layout wiring, lifecycle and event handlers."""

import copy
from typing import Any, Dict, Optional

from textual.binding import Binding
from textual.containers import Container, Vertical
from textual.widgets import (
    Button,
    Checkbox,
    ContentSwitcher,
    Input,
    ProgressBar,
    RadioButton,
    RadioSet,
    RichLog,
    Select,
    Static,
    Switch,
    TextArea,
)


from hackagent.interfaces.cli.config import CLIConfig
from hackagent.interfaces.tui.widgets.actions import AgentActionsViewer
from hackagent.interfaces.tui.widgets.logs import AttackLogViewer


from textual.widgets._select import NoSelection

from hackagent.interfaces.tui.views.attacks.helpers import (
    _ENDPOINT_OPTIONAL_AGENT_TYPES,
    _default_campaign_attack_keys,
)
from hackagent.interfaces.tui.views.attacks.executor import AttacksExecutorMixin
from hackagent.interfaces.tui.views.attacks.form import AttacksFormMixin
from hackagent.interfaces.tui.views.attacks.layout import AttacksLayoutMixin
from hackagent.interfaces.tui.views.attacks.rows import AttackRow, JudgeRow
from hackagent.interfaces.tui.views.attacks.runner import AttacksRunnerMixin


class AttacksTab(
    AttacksLayoutMixin,
    AttacksFormMixin,
    AttacksRunnerMixin,
    AttacksExecutorMixin,
    Container,
):
    """Execute and manage security attacks with a declarative campaign form."""

    DEFAULT_CSS = """
    AttacksTab {
        layout: horizontal;
    }

    AttacksTab #attack-form-container {
        width: 42%;
        layout: vertical;
        border-right: solid $primary;
        padding: 1 2;
    }

    AttacksTab #attack-monitor-container {
        width: 58%;
    }

    /* The wizard column: a fixed progress line + error line on top, the
       active step filling the middle (and scrolling), and the Back/Next bar
       pinned at the bottom. */
    AttacksTab #wizard-progress {
        height: auto;
        text-align: center;
        margin-bottom: 1;
    }

    AttacksTab #wizard-steps {
        height: 1fr;
    }

    AttacksTab #wizard-steps > VerticalScroll {
        height: 1fr;
    }

    AttacksTab #wizard-nav {
        height: auto;
        margin-top: 1;
    }

    AttacksTab #wizard-nav Button {
        width: 1fr;
        margin: 0 1;
    }

    AttacksTab #run-buttons,
    AttacksTab #run-buttons-secondary {
        height: auto;
    }

    AttacksTab #run-buttons Button,
    AttacksTab #run-buttons-secondary Button {
        width: 1fr;
        margin: 0 1;
    }

    AttacksTab #run-summary {
        height: auto;
        border: round $primary;
        padding: 0 1;
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

    AttacksTab #attack-rows,
    AttacksTab #judge-rows {
        height: auto;
    }

    AttacksTab .attack-row,
    AttacksTab .judge-row {
        height: auto;
        border: round $primary;
        padding: 0 1;
        margin-bottom: 1;
    }

    /* A bare Vertical defaults to height: 1fr, so the Parameters container
       ballooned to fill the viewport when expanded — the oversized rows then
       overlapped. Size the row boxes to their content instead. */
    AttacksTab .row-head,
    AttacksTab .row-params {
        height: auto;
    }

    AttacksTab .row-attack-type,
    AttacksTab .row-judge-id {
        width: 1fr;
    }

    AttacksTab .remove-row {
        width: 5;
        min-width: 5;
    }

    AttacksTab .row-attack-desc {
        color: $text-muted;
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

    #: Wizard steps: ContentSwitcher child id → short label.
    _STEPS = ("step-target", "step-attacks", "step-judges", "step-run")
    _STEP_LABELS = ("Target", "Attacks", "Judges", "Run")

    def __init__(self, cli_config: CLIConfig, initial_data: Optional[dict] = None):
        """Initialize attacks tab.

        Args:
            cli_config: CLI configuration object
            initial_data: Initial data to pre-fill form fields
        """
        super().__init__()
        self.cli_config = cli_config
        self.initial_data = initial_data or {}
        self._agent_adapter_operational_config: Optional[Dict[str, Any]] = (
            copy.deepcopy(self.initial_data.get("agent_adapter_operational_config"))
        )
        self._reduced_tui_logs = bool(self.initial_data.get("reduced_tui_logs", False))
        self._step_index = 0

    def on_mount(self) -> None:
        """Called when the tab is mounted."""
        if self.initial_data:
            self._prefill_form()

        self.call_after_refresh(lambda: self._go_to_step(0))
        self.call_after_refresh(self._sync_escalate_visibility)
        self.call_after_refresh(self._add_initial_messages)

        if self.initial_data.get("auto_execute_attack", False):
            self.call_after_refresh(lambda: self._execute_attack(dry_run=False))

    # ------------------------------------------------------------------
    # Wizard navigation
    # ------------------------------------------------------------------

    def _render_step_indicator(self) -> None:
        parts = []
        for index, label in enumerate(self._STEP_LABELS):
            marker = f"{index + 1} {label}"
            if index == self._step_index:
                parts.append(f"[reverse bold] {marker} [/]")
            else:
                parts.append(f"[dim]{marker}[/dim]")
        try:
            self.query_one("#wizard-progress", Static).update("  →  ".join(parts))
        except Exception:
            pass

    def _go_to_step(self, index: int) -> None:
        """Show wizard step *index* and sync the indicator and nav buttons."""
        index = max(0, min(index, len(self._STEPS) - 1))
        self._step_index = index
        try:
            switcher = self.query_one("#wizard-steps", ContentSwitcher)
            switcher.current = self._STEPS[index]
            self.query_one("#wizard-back", Button).disabled = index == 0
            self.query_one("#wizard-next", Button).disabled = (
                index == len(self._STEPS) - 1
            )
        except Exception:
            pass
        self._render_step_indicator()
        if self._STEPS[index] == "step-run":
            self._render_run_summary()

    def _next_step(self) -> None:
        error = self._validate_step(self._step_index)
        errors_widget = self.query_one("#validation-errors", Static)
        if error:
            errors_widget.update(f"[bold red]{error}[/bold red]")
            return
        errors_widget.update("")
        self._go_to_step(self._step_index + 1)

    def _validate_step(self, index: int) -> Optional[str]:
        """A light check gating the Next button for step *index*."""
        step = self._STEPS[index]
        if step == "step-target":
            if not self.query_one("#agent-name", Input).value.strip():
                return "Target: an agent name is required."
            agent_type = self.query_one("#agent-type", Select).value
            if isinstance(agent_type, NoSelection) or not agent_type:
                return "Target: select an agent type."
            endpoint = self.query_one("#endpoint-url", Input).value.strip()
            if not endpoint and str(agent_type) not in _ENDPOINT_OPTIONAL_AGENT_TYPES:
                return "Target: an endpoint URL is required for this agent type."
        elif step == "step-attacks":
            rows = list(self.query(AttackRow))
            if not rows or any(row.attack_type() is None for row in rows):
                return "Attacks: give every attack row a technique."
        return None

    def _render_run_summary(self) -> None:
        """A plain-language recap of the configured campaign for the Run step."""
        try:
            name = self.query_one("#agent-name", Input).value.strip() or "—"
            agent_type = self.query_one("#agent-type", Select).value
            type_label = "—" if isinstance(agent_type, NoSelection) else str(agent_type)
            attacks = [row.attack_type() or "—" for row in self.query(AttackRow)]
            judges = len(list(self.query(JudgeRow)))
            using_dataset = self.query_one("#radio-dataset", RadioButton).value
            if using_dataset:
                preset = self.query_one("#dataset-preset", Select).value
                source = f"dataset '{preset}'"
            else:
                goals = [
                    line
                    for line in self.query_one(
                        "#attack-goals", TextArea
                    ).text.splitlines()
                    if line.strip()
                ]
                source = f"{len(goals)} inline goal(s)"
            summary = (
                f"[bold]Target:[/bold] {name}  [dim]({type_label})[/dim]\n"
                f"[bold]Input:[/bold] {source}\n"
                f"[bold]Attacks:[/bold] {' → '.join(attacks)}\n"
                f"[bold]Judges:[/bold] {judges}"
            )
            self.query_one("#run-summary", Static).update(summary)
        except Exception:
            pass

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
    # Dynamic rows
    # ------------------------------------------------------------------

    def _sync_escalate_visibility(self) -> None:
        """Show the escalate toggle only when 2+ attacks are configured."""
        try:
            is_chain = len(list(self.query(AttackRow))) > 1
            self.query_one("#escalate-only-mitigated", Checkbox).display = is_chain
            self.query_one("#escalate-only-mitigated-help", Static).display = is_chain
        except Exception:
            pass

    def _mutate_rows(self, awaitable: Any) -> None:
        """Await a row mount/remove, then recompute escalate visibility.

        Textual's ``mount``/``remove`` complete on the next message cycle, so
        the row count is only reliable once the returned awaitable resolves.
        """

        async def _finish() -> None:
            await awaitable
            self._sync_escalate_visibility()

        self.run_worker(_finish(), name="attack-rows", exclusive=False)

    def _add_attack_row(self) -> None:
        self._mutate_rows(self.query_one("#attack-rows", Vertical).mount(AttackRow()))

    def _add_judge_row(self) -> None:
        self.query_one("#judge-rows", Vertical).mount(JudgeRow())

    def _remove_row(self, button: Button) -> None:
        """Remove the attack/judge row that owns *button*."""
        for ancestor in button.ancestors:
            if isinstance(ancestor, AttackRow):
                if len(list(self.query(AttackRow))) <= 1:
                    self.query_one("#validation-errors", Static).update(
                        "[bold red]At least one attack is required.[/bold red]"
                    )
                    return
                self._mutate_rows(ancestor.remove())
                return
            if isinstance(ancestor, JudgeRow):
                ancestor.remove()
                return

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

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        button = event.button
        if button.id == "wizard-back":
            self._go_to_step(self._step_index - 1)
        elif button.id == "wizard-next":
            self._next_step()
        elif button.id == "execute-attack":
            self._execute_attack(dry_run=False)
        elif button.id == "dry-run":
            self._execute_attack(dry_run=True)
        elif button.id == "add-attack":
            self._add_attack_row()
        elif button.id == "add-judge":
            self._add_judge_row()
        elif button.has_class("remove-row"):
            self._remove_row(button)
        elif button.id == "clear-form":
            self._clear_form()
        elif button.id == "reset-defaults":
            self._reset_rows()

    def _reset_rows(self) -> None:
        """Restore the default attack campaign and a single judge."""
        attack_container = self.query_one("#attack-rows", Vertical)
        attack_container.remove_children()
        for key in _default_campaign_attack_keys():
            attack_container.mount(AttackRow(key))

        judge_container = self.query_one("#judge-rows", Vertical)
        judge_container.remove_children()
        judge_container.mount(JudgeRow())

        try:
            self.query_one("#judge-aggregation", Select).value = "majority"
            self.query_one("#escalate-only-mitigated", Checkbox).value = True
        except Exception:
            pass
        self.call_after_refresh(self._sync_escalate_visibility)

    def _clear_form(self) -> None:
        """Clear all form fields and restore the default rows."""
        self.query_one("#agent-name", Input).value = ""
        self.query_one("#endpoint-url", Input).value = ""
        self.query_one("#agent-type", Select).value = "google-adk"
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

        self._reset_rows()

        status_widget = self.query_one("#execution-status", Static)
        progress_bar = self.query_one("#attack-progress", ProgressBar)
        status_widget.update("[dim]Configure attack parameters and click Execute[/dim]")
        progress_bar.update(progress=0)
        self.query_one("#validation-errors", Static).update("")

    def refresh_data(self) -> None:
        """Refresh attacks data."""
        pass
