# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Attack execution entry point (validation, spec assembly, worker launch).

The Attacks tab is a declarative :class:`~hackagent.orchestrator.campaign.spec.CampaignSpec`
builder: the form's fields map onto the spec's sections — the target, the
attack rows (each with its own attacker model and parameters), the judge panel,
the guardrails, and the dataset or inline goals — and :meth:`_execute_attack`
hands the assembled spec to the worker, which runs it through
:func:`~hackagent.orchestrator.campaign.run_campaign`.
"""

from typing import Any, Callable, Dict, List, Optional

from textual.widgets import (
    Checkbox,
    Input,
    ProgressBar,
    Select,
    Static,
    Switch,
    TextArea,
)
from textual.widgets._select import NoSelection


from hackagent.interfaces.tui.views.attacks.helpers import (
    _ENDPOINT_OPTIONAL_AGENT_TYPES,
    _escape,
    build_guardrail_config,
    model_config_from_fields,
)
from hackagent.interfaces.tui.views.attacks.rows import AttackRow, JudgeRow


class AttacksRunnerMixin:
    """Attack execution entry point (validation, spec assembly, worker launch).

    Mixed into :class:`~hackagent.interfaces.tui.views.attacks.tab.AttacksTab`.
    """

    def _execute_attack(self, dry_run: bool = False) -> None:
        """Assemble the campaign spec from the form and run (or preview) it.

        Args:
            dry_run: Validate and show the spec without sending any request.
        """
        agent_name = self.query_one("#agent-name", Input).value
        agent_type_raw = self.query_one("#agent-type", Select).value
        endpoint = self.query_one("#endpoint-url", Input).value
        timeout = self.query_one("#timeout", Input).value

        errors_widget = self.query_one("#validation-errors", Static)

        def _reject(message: str) -> None:
            errors_widget.update(f"[bold red]{message}[/bold red]")

        agent_type = (
            "" if isinstance(agent_type_raw, NoSelection) else str(agent_type_raw)
        )

        # ── Basic validation ──
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
        attack_rows = list(self.query(AttackRow))
        if not attack_rows:
            _reject("Add at least one attack.")
            return
        try:
            timeout_int = int(timeout)
            if timeout_int <= 0:
                _reject("Timeout must be a positive integer.")
                return
        except ValueError:
            _reject("Timeout must be a positive integer.")
            return

        errors_widget.update("")  # clear previous errors

        campaign = self._build_campaign_spec(
            agent_name=agent_name,
            agent_type=agent_type,
            endpoint=endpoint,
            timeout=timeout_int,
            attack_rows=attack_rows,
            reject=_reject,
        )
        if campaign is None:
            return

        strategy_label = " → ".join(block["name"] for block in campaign["attacks"])
        status_widget = self.query_one("#execution-status", Static)
        progress_bar = self.query_one("#attack-progress", ProgressBar)

        if dry_run:
            import json

            config_preview = json.dumps(campaign, indent=2, default=str)
            status_widget.update(
                f"""[bold yellow]Dry Run Mode[/bold yellow]

[bold]Agent:[/bold] {_escape(agent_name)}
[bold]Type:[/bold] {_escape(agent_type)}
[bold]Endpoint:[/bold] {_escape(endpoint)}
[bold]Attacks:[/bold] {_escape(strategy_label)}
[bold]Timeout:[/bold] {timeout}s

[bold]Campaign spec:[/bold]
{_escape(config_preview)}

[green]✅ Configuration validation passed[/green]
[dim]Remove dry-run flag to execute the attack[/dim]"""
            )
            return

        status_widget.update(
            f"""[bold cyan]🚀 Initializing Attack...[/bold cyan]

[bold]Agent:[/bold] {_escape(agent_name)}
[bold]Type:[/bold] {_escape(agent_type)}
[bold]Endpoint:[/bold] {_escape(endpoint)}
[bold]Attacks:[/bold] {_escape(strategy_label)}
[bold]Timeout:[/bold] {timeout}s

[yellow]⏳ Connecting to agent and preparing attack...[/yellow]"""
        )

        progress_bar.update(progress=5)

        try:
            self.run_worker(
                lambda: self._run_attack_async(campaign, strategy_label=strategy_label),
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

    # ------------------------------------------------------------------
    # Campaign spec assembly
    # ------------------------------------------------------------------

    def _build_campaign_spec(
        self,
        *,
        agent_name: str,
        agent_type: str,
        endpoint: str,
        timeout: int,
        attack_rows: List[AttackRow],
        reject: Callable[[str], None],
    ) -> Optional[Dict[str, Any]]:
        """Assemble a campaign spec dict from the form, or ``None`` if rejected.

        Every field maps onto a spec section. Each attack row contributes one
        attack with its own attacker model and parameters; the judge rows form
        the evaluation panel; the guardrails wrap the target; the dataset is a
        preset selection or inline goals. A :func:`reject` call writes a
        validation error and returns ``None``.
        """
        dataset = self._dataset_section(reject)
        if dataset is None:
            return None

        attacks: List[Dict[str, Any]] = []
        for row in attack_rows:
            block, error = row.to_block()
            if error:
                reject(error)
                return None
            attacks.append(block)

        target = model_config_from_fields(
            agent_name,
            agent_type,
            endpoint,
            options=self._agent_adapter_operational_config or None,
        )

        # Chain mode escalates: a goal drops out once an attack jailbreaks it,
        # so later attacks only face the goals still standing.
        escalate = (
            len(attack_rows) > 1
            and self.query_one("#escalate-only-mitigated", Checkbox).value
        )

        campaign: Dict[str, Any] = {
            "version": 1,
            "campaign": {
                "name": "TUI — " + " → ".join(block["name"] for block in attacks)
            },
            "dataset": dataset,
            "target": target,
            "attacks": attacks,
            "execution": {
                "escalate": escalate,
                "per_attack_timeout": timeout,
                "on_error": "continue",
            },
        }

        guardrails = self._guardrails_section()
        if guardrails:
            campaign["guardrails"] = guardrails

        evaluation = self._evaluation_section()
        if evaluation:
            campaign["evaluation"] = evaluation

        return campaign

    def _dataset_section(
        self, reject: Callable[[str], None]
    ) -> Optional[Dict[str, Any]]:
        """The campaign ``dataset`` block: a preset selection or inline goals."""
        from textual.widgets import RadioButton

        using_dataset = self.query_one("#radio-dataset", RadioButton).value
        if using_dataset:
            preset_raw = self.query_one("#dataset-preset", Select).value
            if isinstance(preset_raw, NoSelection) or not preset_raw:
                reject("Select a dataset preset.")
                return None
            selection: Dict[str, Any] = {}
            try:
                selection["limit"] = int(self.query_one("#dataset-limit", Input).value)
            except (ValueError, TypeError):
                pass
            selection["shuffle"] = self.query_one("#dataset-shuffle", Switch).value
            try:
                selection["seed"] = int(self.query_one("#dataset-seed", Input).value)
            except (ValueError, TypeError):
                pass
            return {"preset": str(preset_raw), "selection": selection}

        text = self.query_one("#attack-goals", TextArea).text
        goals = [line.strip() for line in text.splitlines() if line.strip()]
        if not goals:
            reject("Enter at least one attack goal, or switch to a dataset.")
            return None
        return {"source": {"type": "inline", "goals": goals}}

    def _guardrails_section(self) -> Dict[str, Any]:
        """The campaign ``guardrails`` block from the before/after form fields."""
        guardrails: Dict[str, Any] = {}
        before = build_guardrail_config(
            self.query_one("#before-gr-name", Input).value,
            self.query_one("#before-gr-type", Select).value,
            self.query_one("#before-gr-endpoint", Input).value,
        )
        after = build_guardrail_config(
            self.query_one("#after-gr-name", Input).value,
            self.query_one("#after-gr-type", Select).value,
            self.query_one("#after-gr-endpoint", Input).value,
        )
        if before:
            guardrails["before"] = before
        if after:
            guardrails["after"] = after
        return guardrails

    def _evaluation_section(self) -> Dict[str, Any]:
        """The campaign ``evaluation`` block from the judge rows + aggregation."""
        judges = [
            config
            for row in self.query(JudgeRow)
            if (config := row.to_config()) is not None
        ]
        if not judges:
            return {}
        aggregation = self.query_one("#judge-aggregation", Select).value
        evaluation: Dict[str, Any] = {"judges": judges}
        if not isinstance(aggregation, NoSelection) and aggregation:
            evaluation["aggregation"] = str(aggregation)
        return evaluation
