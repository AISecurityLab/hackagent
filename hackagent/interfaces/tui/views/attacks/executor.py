# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Background attack worker used by the Attacks tab."""

from typing import Any, Dict, List, Optional

from textual.widgets import (
    Input,
    ProgressBar,
    Select,
    Static,
)


from hackagent.interfaces.tui.widgets.actions import AgentActionsViewer
from hackagent.interfaces.tui.widgets.logs import AttackLogViewer


from hackagent.interfaces.tui.views.attacks.helpers import (
    _escape,
    build_guardrail_config,
)


class AttacksExecutorMixin:
    """Background attack worker used by the Attacks tab.

    Mixed into :class:`~hackagent.interfaces.tui.views.attacks.tab.AttacksTab`.
    """

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
        import time

        from hackagent import AgentType, HackAgent, Settings

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

        from hackagent.interfaces.tui.events import TUIEventBus

        tui_event_bus = TUIEventBus()
        actions_viewer.subscribe_to_bus(tui_event_bus, self.app)

        def on_event(event_type: str, **payload: Any) -> None:
            tui_event_bus.emit(event_type, **payload)

        try:
            agent_type_enum = AgentType.parse(agent_type)

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

            before_guardrail = build_guardrail_config(
                before_gr_name,
                self.query_one("#before-gr-type", Select).value,
                self.query_one("#before-gr-endpoint", Input).value,
            )
            after_guardrail = build_guardrail_config(
                after_gr_name,
                self.query_one("#after-gr-type", Select).value,
                self.query_one("#after-gr-endpoint", Input).value,
            )

            session = HackAgent(
                Settings.resolve(
                    api_key=self.cli_config.api_key or "",
                    base_url=self.cli_config.base_url,
                ),
                timeout=5.0,
            )
            agent = session.target(
                endpoint,
                agent_type_enum,
                name=agent_name,
                guardrails={"before": before_guardrail, "after": after_guardrail},
                adapter_operational_config=self._agent_adapter_operational_config,
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
                        on_event=on_event,
                    )
                else:
                    results = agent.hack(
                        attack_config=attack_config,
                        run_config_override={"timeout": timeout},
                        fail_on_run_error=True,
                        on_event=on_event,
                    )
            finally:
                tui_event_bus.unsubscribe(_on_bus_event)

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

