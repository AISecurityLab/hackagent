# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Widget layout (``compose``) for the Attacks tab."""

from typing import List

from textual.app import ComposeResult
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
    Select,
    SelectionList,
    Static,
    Switch,
    TabbedContent,
    TabPane,
    TextArea,
)

from hackagent.datasets.presets import PRESETS as _DATASET_PRESETS

from hackagent.cli.tui.attack_specs import (
    get_all_attack_specs,
)
from hackagent.cli.tui.widgets.actions import AgentActionsViewer
from hackagent.cli.tui.widgets.logs import AttackLogViewer


from hackagent.cli.tui.views.attacks.helpers import (
    _AGENT_TYPE_CHOICES,
    _default_campaign_attack_keys,
)


class AttacksLayoutMixin:
    """Widget layout (``compose``) for the Attacks tab.

    Mixed into :class:`~hackagent.cli.tui.views.attacks.tab.AttacksTab`.
    """

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
                yield Static("[bold]Attacks[/bold]", classes="section-title")
                yield Static(
                    "[dim]Select one attack, or check multiple to chain them. "
                    "Check order sets the chain order. Defaults to the Jailbreak "
                    "evaluation campaign (h4rm3l → TAP → PAIR).[/dim]"
                )
                yield SelectionList(*strategy_choices, id="attack-strategies")
                yield Static("")

                yield Checkbox(
                    "Escalate only mitigated goals to the next attack",
                    id="escalate-only-mitigated",
                    value=True,
                )
                yield Static(
                    "[dim]Chain mode (2+ attacks checked): a goal moves to "
                    "the next attack only if the previous one mitigated it; "
                    "goals that are already vulnerable are dropped. Uncheck to "
                    "instead run every checked attack against every goal.[/dim]",
                    id="escalate-only-mitigated-help",
                )
                yield Static("")

                yield Label("Configuring attack:")
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
