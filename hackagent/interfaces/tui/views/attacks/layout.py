# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Widget layout (``compose``) for the Attacks tab.

The form is a guided wizard: a :class:`ContentSwitcher` shows one step at a
time — Target, Attacks, Judges, Run — so only one focused screen is on display
instead of one long scroll. Every step's widgets stay mounted, so the spec
assembly in ``runner.py`` can read them all regardless of the active step.
"""

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.widgets import (
    Button,
    Checkbox,
    Collapsible,
    ContentSwitcher,
    Input,
    Label,
    ProgressBar,
    RadioButton,
    RadioSet,
    Select,
    Static,
    Switch,
    TabbedContent,
    TabPane,
    TextArea,
)

from hackagent.client import presets as dataset_presets
from hackagent.interfaces.tui.widgets.actions import AgentActionsViewer
from hackagent.interfaces.tui.widgets.logs import AttackLogViewer


from hackagent.interfaces.tui.views.attacks.helpers import (
    _AGENT_TYPE_CHOICES,
    _default_campaign_attack_keys,
)
from hackagent.interfaces.tui.views.attacks.rows import AttackRow, JudgeRow


class AttacksLayoutMixin:
    """Widget layout (``compose``) for the Attacks tab.

    Mixed into :class:`~hackagent.interfaces.tui.views.attacks.tab.AttacksTab`.
    """

    def compose(self) -> ComposeResult:
        """Compose the attacks wizard."""
        campaign_keys = _default_campaign_attack_keys()

        with Horizontal():
            # ── Left side: the guided wizard ──
            with Vertical(id="attack-form-container"):
                yield Static("", id="wizard-progress")
                yield Static("", id="validation-errors", classes="validation-errors")

                with ContentSwitcher(initial="step-target", id="wizard-steps"):
                    # ── Step 1: Target ──
                    with VerticalScroll(id="step-target"):
                        yield Static(
                            "[bold cyan]Step 1 · Target[/bold cyan]  "
                            "[dim]Who are you attacking?[/dim]"
                        )
                        yield Static("")
                        with Collapsible(title="Target Agent", collapsed=False):
                            yield Label("Agent Name:")
                            yield Input(
                                placeholder="e.g., weather-bot", id="agent-name"
                            )
                            yield Label("Agent Type:")
                            yield Select(
                                _AGENT_TYPE_CHOICES, id="agent-type", value="google-adk"
                            )
                            yield Label("Endpoint URL:")
                            yield Input(
                                placeholder="e.g., http://localhost:8000",
                                id="endpoint-url",
                            )
                        with Collapsible(
                            title="Before Guardrail (optional)", collapsed=True
                        ):
                            yield Static(
                                "[dim]Checks prompts before they reach the "
                                "target.[/dim]"
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
                        with Collapsible(
                            title="After Guardrail (optional)", collapsed=True
                        ):
                            yield Static(
                                "[dim]Checks responses after the target "
                                "generates them.[/dim]"
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
                        yield Static("[bold]Input Source[/bold]")
                        with RadioSet(id="input-source-radio"):
                            yield RadioButton("Goals", value=True, id="radio-goals")
                            yield RadioButton("Dataset", id="radio-dataset")
                        with Vertical(id="goals-container"):
                            yield Label("Goals (one per line):")
                            goals_area = TextArea(
                                "Return fake weather data", id="attack-goals"
                            )
                            goals_area.styles.height = 5
                            yield goals_area
                        with Vertical(id="dataset-container"):
                            yield Label("Dataset:")
                            dataset_choices = [
                                (k, k) for k in sorted(dataset_presets())
                            ]
                            yield Select(
                                dataset_choices, id="dataset-preset", value="harmbench"
                            )
                            yield Label("Limit (max samples):")
                            yield Input(value="5", id="dataset-limit")
                            yield Label("Shuffle:")
                            yield Switch(value=True, id="dataset-shuffle")
                            yield Label("Seed:")
                            yield Input(value="42", id="dataset-seed")
                        yield Static("")
                        yield Label("Timeout (seconds):")
                        yield Input(value="300", id="timeout")

                    # ── Step 2: Attacks ──
                    with VerticalScroll(id="step-attacks"):
                        yield Static(
                            "[bold cyan]Step 2 · Attacks[/bold cyan]  "
                            "[dim]Which attacks to run?[/dim]"
                        )
                        yield Static(
                            "[dim]Each attack carries its own attacker model and "
                            "parameters. Add 2+ to run them as an escalating "
                            "campaign.[/dim]"
                        )
                        yield Static("")
                        with Vertical(id="attack-rows"):
                            for key in campaign_keys:
                                yield AttackRow(key)
                        yield Button(
                            "➕ Add Attack", id="add-attack", variant="success"
                        )
                        yield Static("")
                        yield Checkbox(
                            "Escalate: drop a goal once an attack jailbreaks it",
                            id="escalate-only-mitigated",
                            value=True,
                        )
                        yield Static(
                            "[dim]With 2+ attacks, a solved goal drops out so "
                            "later attacks only face the goals still standing. "
                            "Uncheck to run every attack against every goal.[/dim]",
                            id="escalate-only-mitigated-help",
                        )

                    # ── Step 3: Judges ──
                    with VerticalScroll(id="step-judges"):
                        yield Static(
                            "[bold cyan]Step 3 · Judges[/bold cyan]  "
                            "[dim]How are replies scored?[/dim]"
                        )
                        yield Static(
                            "[dim]Each reply is scored by the judge panel. Add "
                            "judges and choose how their votes combine into one "
                            "verdict.[/dim]"
                        )
                        yield Static("")
                        with Vertical(id="judge-rows"):
                            yield JudgeRow()
                        yield Button("➕ Add Judge", id="add-judge", variant="success")
                        yield Static("")
                        yield Label("Aggregation:")
                        yield Select(
                            [
                                ("Majority", "majority"),
                                ("Mean", "mean"),
                                ("Max", "max"),
                                ("Any", "any"),
                            ],
                            id="judge-aggregation",
                            value="majority",
                        )

                    # ── Step 4: Run ──
                    with VerticalScroll(id="step-run"):
                        yield Static(
                            "[bold cyan]Step 4 · Run[/bold cyan]  "
                            "[dim]Review and launch.[/dim]"
                        )
                        yield Static("")
                        yield Static("", id="run-summary")
                        yield Static("")
                        with Horizontal(id="run-buttons"):
                            yield Button(
                                "▶ Execute", id="execute-attack", variant="primary"
                            )
                            yield Button("Dry Run", id="dry-run", variant="default")
                        with Horizontal(id="run-buttons-secondary"):
                            yield Button(
                                "Reset", id="reset-defaults", variant="warning"
                            )
                            yield Button("Clear", id="clear-form", variant="error")
                        yield Static("")
                        yield Static(
                            "[dim]Configure the steps and click Execute[/dim]",
                            id="execution-status",
                        )
                        yield ProgressBar(
                            total=100, show_eta=True, id="attack-progress"
                        )

                # ── Wizard navigation ──
                with Horizontal(id="wizard-nav"):
                    yield Button("◀ Back", id="wizard-back", variant="default")
                    yield Button("Next ▶", id="wizard-next", variant="primary")

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
