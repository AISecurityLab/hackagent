# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Background attack worker used by the Attacks tab.

The worker runs an assembled :class:`~hackagent.orchestrator.campaign.spec.CampaignSpec`
through :func:`~hackagent.orchestrator.campaign.run_campaign`, writing results to
the session's local store so the Results tab can read them. Progress tracks the
campaign's lifecycle events: ``attack_started`` (with ``expected_goals``), a
``goal_finished`` per goal, and ``attack_finished``.
"""

from typing import Any, Dict

from textual.widgets import (
    ProgressBar,
    Static,
)


from hackagent.interfaces.tui.widgets.actions import AgentActionsViewer
from hackagent.interfaces.tui.widgets.logs import AttackLogViewer


from hackagent.interfaces.tui.views.attacks.helpers import _escape


class AttacksExecutorMixin:
    """Background attack worker used by the Attacks tab.

    Mixed into :class:`~hackagent.interfaces.tui.views.attacks.tab.AttacksTab`.
    """

    def _run_attack_async(
        self,
        campaign: Dict[str, Any],
        *,
        strategy_label: str = "",
    ) -> None:
        """Run an assembled campaign spec in a background thread.

        Args:
            campaign: The campaign spec dict assembled from the form.
            strategy_label: Human-readable attack name(s) for status text.
        """
        import time

        from hackagent import HackAgent, Settings
        from hackagent.orchestrator.campaign import run_campaign

        target = campaign.get("target") or {}
        agent_name = str(target.get("name", "target"))

        status_widget = self.query_one("#execution-status", Static)
        progress_bar = self.query_one("#attack-progress", ProgressBar)
        log_viewer = self.query_one("#attack-log-viewer", AttackLogViewer)
        actions_viewer = self.query_one("#attack-actions-viewer", AgentActionsViewer)

        # Clear previous logs and actions
        self.app.call_from_thread(log_viewer.clear_logs)
        self.app.call_from_thread(actions_viewer.clear_actions)
        self.app.call_from_thread(
            log_viewer.add_log,
            f"🚀 Starting campaign for agent: {agent_name}",
            "INFO",
        )
        self.app.call_from_thread(
            actions_viewer.add_step_separator,
            f"Campaign: {agent_name}",
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

        strategy_name = strategy_label or "attack"
        total_attacks = len(campaign.get("attacks") or ()) or 1

        try:
            self.app.call_from_thread(progress_bar.update, progress=10)
            self.app.call_from_thread(
                status_widget.update,
                f"""[bold cyan]🔧 Initializing campaign...[/bold cyan]

[bold]Agent:[/bold] {_escape(agent_name)}
[bold]Attacks:[/bold] {_escape(strategy_name)}

[yellow]⏳ Setting up attack infrastructure...[/yellow]
[dim]Progress: 10%[/dim]""",
            )

            session = HackAgent(
                Settings.resolve(
                    api_key=self.cli_config.api_key or "",
                    base_url=self.cli_config.base_url,
                ),
                timeout=5.0,
            )

            # Event-driven progress: each attack owns an equal slice of the
            # 10→95% band; within its slice the bar fills as its goals finish.
            # The campaign emits ``expected_goals`` on ``attack_started`` and a
            # ``goal_finished`` per goal — all the runner knows to report.
            band = 85.0 / total_attacks
            state = {"index": -1, "expected": 0, "done": 0}

            def _progress_pct() -> int:
                if state["expected"] > 0:
                    frac = min(state["done"] / state["expected"], 1.0)
                else:
                    frac = min(state["done"] * 0.2, 0.9)
                return 10 + int(band * (state["index"] + frac))

            def _on_bus_event(event: Any) -> None:
                et = event.event_type
                payload = event.payload or {}

                if et == "attack_started":
                    state["index"] += 1
                    state["expected"] = int(payload.get("expected_goals") or 0)
                    state["done"] = 0
                    attack = _escape(str(payload.get("attack", strategy_name)))
                    self.app.call_from_thread(
                        progress_bar.update, progress=_progress_pct()
                    )
                    self.app.call_from_thread(
                        status_widget.update,
                        f"""[bold cyan]⚔️ Executing {attack}...[/bold cyan]

[bold]Goals to process:[/bold] {state["expected"] or "unknown"}

[yellow]⏳ Attack running...[/yellow]
[dim]Progress: {_progress_pct()}%[/dim]""",
                    )
                    return

                if et == "goal_finished":
                    state["done"] += 1
                    pct = _progress_pct()
                    success = bool(payload.get("success"))
                    icon = "✓" if success else "✗"
                    elapsed = payload.get("elapsed_s")
                    elapsed_s = (
                        f" ({elapsed:.1f}s)"
                        if isinstance(elapsed, (int, float))
                        else ""
                    )
                    expected = state["expected"]
                    summary = (
                        f"Goal {state['done']}"
                        + (f"/{expected}" if expected else "")
                        + f"  {icon}{elapsed_s}"
                    )
                    self.app.call_from_thread(progress_bar.update, progress=pct)
                    self.app.call_from_thread(
                        status_widget.update,
                        f"""[bold cyan]⚔️ Executing {_escape(strategy_name)}...[/bold cyan]

[bold]Last:[/bold] {summary}

[yellow]⏳ Attack running...[/yellow]
[dim]Progress: {pct}%[/dim]""",
                    )

            tui_event_bus.subscribe(_on_bus_event)

            start_time = time.time()
            try:
                result = run_campaign(
                    campaign, on_event=on_event, store=session.backend
                )
            finally:
                tui_event_bus.unsubscribe(_on_bus_event)

            duration = time.time() - start_time
            self.app.call_from_thread(progress_bar.update, progress=100)

            attempts = sum(len(outcome.attempts) for outcome in result.attacks)
            successes = sum(
                1
                for outcome in result.attacks
                for attempt in outcome.attempts
                if attempt.verdict is not None and attempt.verdict.success
            )
            errored = [outcome.name for outcome in result.attacks if outcome.error]
            error_note = (
                f"\n[bold]Attacks with errors:[/bold] {_escape(', '.join(errored))}"
                if errored
                else ""
            )
            storage_note = "[dim]Results saved locally → ~/.local/share/hackagent/hackagent.db[/dim]"
            self.app.call_from_thread(
                status_widget.update,
                f"""[bold green]✅ Campaign Completed![/bold green]

[bold]Agent:[/bold] {_escape(agent_name)}
[bold]Duration:[/bold] {duration:.1f} seconds
[bold]Attacks:[/bold] {len(result.attacks)}
[bold]Attempts:[/bold] {attempts}
[bold]Successes:[/bold] {successes}{error_note}

[green]Campaign finished![/green]
[dim]Check the Results tab to view detailed attack results.[/dim]
{storage_note}""",
            )

        except Exception as e:
            key_hint = "[dim]Ensure the agent endpoint is accessible.[/dim]"
            self.app.call_from_thread(progress_bar.update, progress=0)
            self.app.call_from_thread(
                status_widget.update,
                f"""[bold red]❌ Campaign Failed[/bold red]

[bold]Agent:[/bold] {_escape(agent_name)}
[bold]Error:[/bold] {_escape(str(e))}

[red]Campaign execution encountered an error.[/red]
[dim]Please check your configuration and try again.[/dim]
{key_hint}""",
            )
