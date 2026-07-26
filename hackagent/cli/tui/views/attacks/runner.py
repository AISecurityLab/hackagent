# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Attack execution entry point (validation + worker launch)."""

import copy
from typing import Any, Dict, List, Optional

from textual.widgets import (
    Checkbox,
    Input,
    ProgressBar,
    RadioButton,
    Select,
    SelectionList,
    Static,
    Switch,
    TextArea,
)
from textual.widgets._select import NoSelection


from hackagent.cli.tui.attack_specs import (
    get_attack_config_spec,
)


from hackagent.cli.tui.views.attacks.helpers import (
    _ENDPOINT_OPTIONAL_AGENT_TYPES,
    _escape,
)


class AttacksRunnerMixin:
    """Attack execution entry point (validation + worker launch).

    Mixed into :class:`~hackagent.cli.tui.views.attacks.tab.AttacksTab`.
    """

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
