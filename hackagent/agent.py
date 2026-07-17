# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from hackagent.logger import get_logger
from typing import TYPE_CHECKING, Any, Dict, Optional, Union

from hackagent import utils
from hackagent.errors import HackAgentError
from hackagent.router import AgentRouter
from hackagent.router.types import AgentTypeEnum

# Lazy import for attack orchestrators to avoid ~0.5s startup delay
if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


def _resolve_target_config(target_config: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Return normalized victim request defaults for the configured router."""
    from hackagent.attacks.techniques.config import default_target

    resolved = default_target()
    if not target_config:
        return resolved

    merged = {key: value for key, value in target_config.items() if value is not None}
    if "request_timeout" in merged and "timeout" not in merged:
        merged["timeout"] = merged.pop("request_timeout")

    resolved.update(merged)
    return resolved


class HackAgent:
    """
    The primary client for orchestrating security assessments with HackAgent.

    This class serves as the main entry point to the HackAgent library, providing
    a high-level interface for:
    - Configuring victim agents that will be assessed.
    - Defining and selecting attack strategies.
    - Executing automated security tests against the configured agents.
    - Retrieving and handling test results.

    It encapsulates complexities such as agent registration
    with the local backend (via `AgentRouter`), and the dynamic dispatch of various
    attack methodologies.

    Attributes:
        router: An `AgentRouter` instance managing the agent's representation
            in the HackAgent backend.
        attack_strategies: A dictionary mapping strategy names to their
            `AttackStrategy` implementations.
    """

    def __init__(
        self,
        endpoint: str,
        name: Optional[str] = None,
        agent_type: Union[AgentTypeEnum, str] = AgentTypeEnum.UNKNOWN,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        raise_on_unexpected_status: bool = False,
        timeout: Optional[float] = 120.0,
        metadata: Optional[Dict[str, Any]] = None,
        target_config: Optional[Dict[str, Any]] = None,
        adapter_operational_config: Optional[Dict[str, Any]] = None,
        thinking: Optional[bool] = None,
        before_guardrail: Optional[Dict[str, Any]] = None,
        after_guardrail: Optional[Dict[str, Any]] = None,
    ):
        """
        Initializes the HackAgent client and prepares it for interaction.

        This constructor sets up the local storage backend, loads default
        prompts, resolves the agent type, and initializes the agent router
        to ensure the agent is known to the backend. It also prepares available
        attack strategies.

        Args:
            endpoint: The target application's endpoint URL. This is the primary
                interface that the configured agent will interact with or represent
                during security tests.
            name: An optional descriptive name for the agent being configured.
                If not provided, a default name might be assigned or behavior might
                depend on the specific backend agent management policies.
            agent_type: Specifies the type of the agent. This can be provided
                as an `AgentTypeEnum` member (e.g., `AgentTypeEnum.GOOGLE_ADK`) or
                as a string identifier (e.g., "google-adk", "litellm").
                String values are automatically converted to the corresponding
                `AgentTypeEnum` member. Defaults to `AgentTypeEnum.UNKNOWN` if
                not specified or if an invalid string is provided.
            raise_on_unexpected_status: If set to `True`, the API client will
                raise an exception for any HTTP status codes that are not typically
                expected for a successful operation. Defaults to `False`.
            timeout: The timeout duration in seconds for API requests made by the
                authenticated (remote) HackAgent backend client. Defaults to
                `120.0` seconds so requests to a misbehaving/unreachable backend
                fail predictably instead of hanging indefinitely. Pass `None`
                explicitly to opt out and disable the timeout (unbounded wait,
                the previous default behavior).
            metadata: Optional dictionary containing agent-specific metadata.
            target_config: Optional default request settings for the configured
                victim model. This is the preferred place to define target-side
                generation defaults such as `max_tokens`, `temperature`,
                and `timeout`.
            adapter_operational_config: Optional configuration for the agent adapter.
            thinking: Optional OLLAMA-only control for reasoning traces.
                When set to `False`, requests sent through the target OLLAMA adapter
                include `think: false` to disable thinking output. Ignored for
                non-OLLAMA target agent types.
        """

        resolved_auth_token = utils.resolve_api_token(direct_api_key_param=api_key)

        if resolved_auth_token:
            from hackagent.server.client import AuthenticatedClient
            from hackagent.server.storage.remote import RemoteBackend

            _base_url = base_url or "https://api.hackagent.dev"
            _client = AuthenticatedClient(
                base_url=_base_url,
                token=resolved_auth_token,
                prefix="Bearer",
                raise_on_unexpected_status=raise_on_unexpected_status,
                timeout=timeout,
            )
            self.backend = RemoteBackend(_client)
            logger.info("HackAgent using remote backend → %s", _base_url)
        else:
            from hackagent.server.storage.local import LocalBackend

            self.backend = LocalBackend()
            logger.info(
                "HackAgent using local backend → ~/.local/share/hackagent/hackagent.db"
            )

        # Backward compatible raw HTTP client reference.
        self.client = getattr(self.backend, "_client", None)

        processed_agent_type = utils.resolve_agent_type(agent_type)
        self.target_config = _resolve_target_config(target_config)
        explicit_target_config = (
            {
                key: value
                for key, value in (target_config or {}).items()
                if value is not None
            }
            if target_config
            else {}
        )

        router_metadata = {
            key: value
            for key, value in {**(metadata or {}), **explicit_target_config}.items()
            if value is not None
        }
        router_operational_config = {
            **self.target_config,
            **(adapter_operational_config or {}),
        }

        if processed_agent_type == AgentTypeEnum.OLLAMA:
            if (
                thinking is not None
                and router_operational_config.get("thinking") is None
            ):
                router_operational_config["thinking"] = thinking
        else:
            # Keep `thinking` strictly OLLAMA-specific.
            router_operational_config.pop("thinking", None)

        self.router = AgentRouter(
            backend=self.backend,
            name=name or endpoint,  # fall back to endpoint if no name provided
            agent_type=processed_agent_type,
            endpoint=endpoint,
            metadata=router_metadata,
            adapter_operational_config=router_operational_config,
        )

        # Wire guardrails onto the router once — they apply transparently to
        # every route_request call for all attacks on this target.
        if before_guardrail or after_guardrail:
            from hackagent.attacks.shared.guardrail import create_guardrail_from_config

            if before_guardrail:
                self.router.before_guardrail = create_guardrail_from_config(
                    before_guardrail, self.backend
                )
                logger.info("before_guardrail active on target router.")
            if after_guardrail:
                self.router.after_guardrail = create_guardrail_from_config(
                    after_guardrail, self.backend
                )
                logger.info("after_guardrail active on target router.")

        # Attack strategies are lazy-loaded to improve startup time
        self._attack_strategies: Optional[Dict[str, Any]] = None

    @property
    def attack_strategies(self) -> Dict[str, Any]:
        """Lazy-loaded attack strategies dictionary."""
        if self._attack_strategies is None:
            # Import here to avoid circular imports and improve startup time
            from hackagent.attacks.registry import (
                AdvPrefixOrchestrator,
                AutoDANTurboOrchestrator,
                BaselineOrchestrator,
                StaticTemplateOrchestrator,
                BoNOrchestrator,
                CipherChatOrchestrator,
                FCOrchestrator,
                tFCOrchestrator,
                H4rm3lOrchestrator,
                RagOrchestrator,
                PAPOrchestrator,
                PAIROrchestrator,
                FlipAttackOrchestrator,
                TAPOrchestrator,
                MMLOrchestrator,
            )

            self._attack_strategies = {
                "advprefix": AdvPrefixOrchestrator(hackagent_agent=self),
                "autodan_turbo": AutoDANTurboOrchestrator(hackagent_agent=self),
                "baseline": BaselineOrchestrator(hackagent_agent=self),
                "static_template": StaticTemplateOrchestrator(hackagent_agent=self),
                "bon": BoNOrchestrator(hackagent_agent=self),
                "cipherchat": CipherChatOrchestrator(hackagent_agent=self),
                "fc": FCOrchestrator(hackagent_agent=self),
                "tfc": tFCOrchestrator(hackagent_agent=self),
                "pair": PAIROrchestrator(hackagent_agent=self),
                "flipattack": FlipAttackOrchestrator(hackagent_agent=self),
                "tap": TAPOrchestrator(hackagent_agent=self),
                "h4rm3l": H4rm3lOrchestrator(hackagent_agent=self),
                "pap": PAPOrchestrator(hackagent_agent=self),
                "rag": RagOrchestrator(hackagent_agent=self),
                "mml": MMLOrchestrator(hackagent_agent=self),
            }
        return self._attack_strategies

    def hack(
        self,
        attack_config: Dict[str, Any],
        run_config_override: Optional[Dict[str, Any]] = None,
        fail_on_run_error: bool = True,
        _tui_event_bus: Optional[Any] = None,
    ) -> Any:
        """
        Executes a specified attack strategy against the configured victim agent.

        This method serves as the primary action command for initiating an attack.
        It identifies the appropriate attack strategy based on `attack_config`,
        ensures the victim agent (managed by `self.router`) is ready, and then
        delegates the execution to the chosen strategy.

        Args:
            attack_config: A dictionary containing parameters specific to the
                chosen attack type. Must include an 'attack_type' key that maps
                to a registered strategy (e.g., "advprefix"). Other keys provide
                configuration for that strategy (e.g., 'category', 'prompt_text').
            run_config_override: An optional dictionary that can override default
                run configurations. The specifics depend on the attack strategy
                and backend capabilities.
            fail_on_run_error: If `True` (the default), an exception will be
                raised if the attack run encounters an error and fails. If `False`,
                errors might be suppressed or handled differently by the strategy.

        Returns:
            The result returned by the `execute` method of the chosen attack
            strategy. The nature of this result is strategy-dependent.

        Raises:
            ValueError: If the 'attack_type' is missing from `attack_config` or
                if the specified 'attack_type' is not a supported/registered
                strategy.
            HackAgentError: For issues during backend
                agent operations, or other unexpected errors during the attack process.
        """
        try:
            attack_type = attack_config.get("attack_type")
            if not attack_type:
                raise ValueError("'attack_type' must be provided in attack_config.")

            strategy = self.attack_strategies.get(attack_type)
            if not strategy:
                supported_types = list(self.attack_strategies.keys())
                raise ValueError(
                    f"Unsupported attack_type: {attack_type}. Supported types: {supported_types}."
                )

            backend_agent = self.router.backend_agent

            logger.info(
                f"Preparing to attack agent '{backend_agent.name}' "
                f"(ID: {backend_agent.id}, Type: {backend_agent.agent_type}) "
                f"configured in this HackAgent instance, using strategy '{attack_type}'."
            )

            return strategy.execute(
                attack_config=attack_config,
                run_config_override=run_config_override,
                fail_on_run_error=fail_on_run_error,
                _tui_event_bus=_tui_event_bus,
            )

        except HackAgentError:
            raise
        except ValueError as ve:
            logger.error(f"Configuration error in HackAgent.hack: {ve}", exc_info=True)
            raise HackAgentError(f"Configuration error: {ve}") from ve
        except RuntimeError as re:
            logger.error(f"Runtime error during HackAgent.hack: {re}", exc_info=True)
            if "Failed to create backend agent" in str(
                re
            ) or "Failed to update metadata" in str(re):
                raise HackAgentError(f"Backend agent operation failed: {re}") from re
            raise HackAgentError(f"An unexpected runtime error occurred: {re}") from re
        except Exception as e:
            logger.error(f"Unexpected error in HackAgent.hack: {e}", exc_info=True)
            raise HackAgentError(
                f"An unexpected error occurred during attack: {e}"
            ) from e

    def hack_chain(
        self,
        attacks: Optional[list] = None,
        goals: Optional[list] = None,
        run_config_override: Optional[Dict[str, Any]] = None,
        fail_on_run_error: bool = True,
        escalate_only_mitigated: bool = True,
        _tui_event_bus: Optional[Any] = None,
    ) -> list:
        """
        Runs a sequence of attack strategies against a shared pool of goals.

        By default (``escalate_only_mitigated=True``) this implements a
        "fallback ladder": every goal starts at ``attacks[0]``. Any goal for
        which the victim's response is judged successful (a jailbreak/
        violation) is considered resolved and is dropped from the chain — it
        is never retried. Any goal that is mitigated (the victim's response
        is judged safe) is carried over and retried with ``attacks[1]``, then
        ``attacks[2]``, and so on, until either the goal succeeds or the
        chain is exhausted.

        With ``escalate_only_mitigated=False``, every goal is instead sent to
        *every* attack in the chain regardless of outcome — useful for
        running several attacks against the same goal set and collecting all
        of their results in one call, rather than escalating only failures.

        Success/mitigation is determined per goal from the evaluated result
        rows returned by each step (see
        ``hackagent.attacks.evaluator.metrics.is_successful_result``): a goal
        is considered successful for a step if *any* of its result rows for
        that step are judged successful.

        Args:
            attacks: Ordered list of ``attack_config`` dicts, one per chain
                step, using the same shape accepted by :meth:`hack` (each
                must include its own ``attack_type`` and any attack-specific
                settings). Only the *first* entry needs to specify how goals
                are sourced (``goals``, ``dataset`` or ``intents``) unless
                the ``goals`` parameter below is provided; subsequent steps
                automatically receive only the goals still mitigated by the
                previous step (or all goals, see ``escalate_only_mitigated``).
                Defaults to ``None``, which resolves to the Jailbreak
                evaluation campaign's primary attacks, in order — ``h4rm3l``
                → ``TAP`` → ``PAIR`` (see
                ``hackagent.risks.jailbreak.JAILBREAK_PROFILE``). A goal
                source is still required either way, via ``goals`` or a
                ``dataset``/``goals``/``intents`` key on the first step.
            goals: Optional explicit list of goal strings to use for the
                whole chain. When provided, it takes precedence over any
                ``goals``/``dataset``/``intents`` set on ``attacks[0]``.
            run_config_override: Optional run configuration overrides applied
                to every step, forwarded to :meth:`hack`.
            fail_on_run_error: Forwarded to :meth:`hack` for every step.
            escalate_only_mitigated: When ``True`` (default), a goal only
                moves on to the next attack if it was mitigated at the
                current step — goals that already succeeded are dropped, and
                each goal's final result is either its first success or its
                last (final) attempt. When ``False``, every goal is sent to
                every attack regardless of outcome, and results from *all*
                steps are kept for every goal (nothing is dropped or
                overwritten).

        Returns:
            A flat list of result rows (same row shape as :meth:`hack`),
            grouped by original goal, in first-seen order. Each row is
            tagged with ``chain_step`` (0-based index into ``attacks``) and
            ``chain_attack_type`` identifying which attack produced it.

        Raises:
            HackAgentError: If ``attacks`` is empty, or a step is missing
                ``attack_type``.
        """
        if attacks is None:
            # Default chain: the Jailbreak evaluation campaign's primary
            # attacks, in campaign order. `technique` strings in the profile
            # (e.g. "TAP", "PAIR") use display casing; `attack_strategies`
            # keys are lowercase, so normalize before use.
            from hackagent.risks.jailbreak import JAILBREAK_PROFILE

            attacks = [
                {"attack_type": rec.technique.strip().lower()}
                for rec in JAILBREAK_PROFILE.primary_attacks
            ]

        if not attacks:
            raise HackAgentError(
                "'attacks' must be a non-empty list of attack_config dicts."
            )

        from hackagent.attacks.evaluator.metrics import is_successful_result

        n_steps = len(attacks)
        remaining_goals: Optional[list] = list(goals) if goals is not None else None
        goal_order: list = list(goals) if goals is not None else []
        final_rows_by_goal: Dict[str, list] = {}

        for step_index, step_config in enumerate(attacks):
            if remaining_goals is not None and not remaining_goals:
                logger.info(
                    "All goals resolved before chain step %d/%d; skipping remaining attack(s).",
                    step_index + 1,
                    n_steps,
                )
                break

            attack_type = step_config.get("attack_type")
            if not attack_type:
                raise HackAgentError(
                    f"hack_chain step {step_index} is missing 'attack_type'."
                )

            step_attack_config = dict(step_config)
            if remaining_goals is not None:
                step_attack_config["goals"] = remaining_goals
                step_attack_config.pop("dataset", None)
                step_attack_config.pop("intents", None)

            logger.info(
                "hack_chain step %d/%d: running '%s' against %s goal(s)",
                step_index + 1,
                n_steps,
                attack_type,
                len(remaining_goals) if remaining_goals is not None else "all",
            )

            # Each step is executed through the same public `hack()` entry
            # point used everywhere else (CLI/TUI/SDK) — hack_chain adds no
            # parallel execution path, it only decides *which* goals each
            # step receives and tags/regroups the returned rows afterwards.
            step_results = self.hack(
                attack_config=step_attack_config,
                run_config_override=run_config_override,
                fail_on_run_error=fail_on_run_error,
                _tui_event_bus=_tui_event_bus,
            )
            step_rows = (
                step_results
                if isinstance(step_results, list)
                else list(step_results or [])
            )

            # Group returned rows by their `goal` text — the same lookup
            # convention used throughout the codebase to associate a result
            # back to its goal (e.g. Tracker.get_goal_context_by_goal,
            # TrackingCoordinator, BaseEvaluationStep's MERGE_KEYS). Every
            # technique preserves the original goal string verbatim in its
            # output rows, so this is a plain, reliable lookup — no need to
            # reconstruct or second-guess it.
            #
            # Grouping (rather than checking each row independently) matters
            # because a single goal can have several rows in one step — not
            # from multiple judges (those are already merged into per-judge
            # columns, e.g. eval_hb/eval_jb, on the *same* row, with the
            # majority vote across them resolved by is_successful_result()
            # before we ever see it here) but from multiple distinct attempts
            # at the same goal (e.g. AdvPrefix's several generated prefixes,
            # BoN's N augmented variants, TAP/PAIR's tree branches), each its
            # own (goal, prefix, completion) row. "Mitigated" means *all* of
            # that goal's attempts failed; "succeeded" means *any* attempt
            # did. A flat `for row in step_rows: if not successful: ...`
            # can't express that OR-across-attempts semantics, and would
            # also append the same goal multiple times (once per failing
            # row) without an explicit dedup step.
            rows_by_goal: Dict[str, list] = {}
            for row in step_rows:
                if not isinstance(row, dict):
                    continue
                row_goal = row.get("goal", "unknown")
                rows_by_goal.setdefault(row_goal, []).append(
                    {**row, "chain_step": step_index, "chain_attack_type": attack_type}
                )

            if remaining_goals is None:
                # First step resolved its own goals internally (via 'goals',
                # 'dataset' or 'intents' on attacks[0]) — dict insertion
                # order already matches first-seen order, so reuse it
                # directly instead of tracking a parallel order list.
                remaining_goals = list(rows_by_goal.keys())
                goal_order = list(remaining_goals)

            next_remaining: list = []
            # Iterate the goals we *sent* this step (`remaining_goals`), not
            # `rows_by_goal`/`step_rows` directly: a goal that comes back
            # with zero rows (e.g. the attack errored on it) must still be
            # looked up here — `rows_by_goal.get(goal, [])` defaults to `[]`,
            # and `not any([])` correctly keeps it mitigated/in-chain. If we
            # only walked what actually came back in `step_rows`, a goal
            # with no response would simply never appear and would silently
            # fall out of the chain, as if it had succeeded.
            for goal in remaining_goals:
                goal_rows = rows_by_goal.get(goal, [])

                if not escalate_only_mitigated:
                    # Every goal proceeds to every attack regardless of
                    # outcome; keep rows from all steps instead of only the
                    # latest attempt.
                    final_rows_by_goal.setdefault(goal, []).extend(goal_rows)
                    next_remaining.append(goal)
                    continue

                if goal_rows:
                    final_rows_by_goal[goal] = goal_rows
                mitigated = not any(is_successful_result(row) for row in goal_rows)
                if mitigated:
                    next_remaining.append(goal)
                else:
                    logger.info(
                        "Goal succeeded at chain step %d ('%s'); dropped from chain: %s",
                        step_index + 1,
                        attack_type,
                        str(goal)[:80],
                    )

            remaining_goals = next_remaining

        if remaining_goals and escalate_only_mitigated:
            logger.info(
                "%d goal(s) mitigated through the entire chain (%d step(s)): %s",
                len(remaining_goals),
                n_steps,
                ", ".join(str(g)[:60] for g in remaining_goals),
            )

        final_results: list = []
        for goal in goal_order:
            final_results.extend(final_rows_by_goal.get(goal, []))
        return final_results
