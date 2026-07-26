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


from hackagent.cli.tui.widgets.actions import AgentActionsViewer
from hackagent.cli.tui.widgets.logs import AttackLogViewer


from hackagent.cli.tui.views.attacks.helpers import (
    _escape,
)


class AttacksExecutorMixin:
    """Background attack worker used by the Attacks tab.

    Mixed into :class:`~hackagent.cli.tui.views.attacks.tab.AttacksTab`.
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
