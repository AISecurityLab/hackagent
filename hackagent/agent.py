# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from hackagent.core.logging import get_logger
from typing import Any, Dict, Optional, Union

from hackagent.attacks._lib.llm_router import LLMRouter
from hackagent.core.contracts import AgentType, ModelSpec
from hackagent.core.errors import HackAgentError
from hackagent.core.settings import Settings
from hackagent.models.client import EnvelopeLLM, connect
from hackagent.models.dispatch import check_supported
from hackagent.models.factory import ModelFactory, spec_from_config
from hackagent.models.guardrail import Guarded, GuardrailSpec, LLMGuardrail

logger = get_logger(__name__)


def _resolve_target_config(target_config: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Return normalized victim request defaults for the configured target."""
    from hackagent.attacks.techniques.config import default_target

    resolved = default_target()
    if not target_config:
        return resolved

    merged = {key: value for key, value in target_config.items() if value is not None}
    if "request_timeout" in merged and "timeout" not in merged:
        merged["timeout"] = merged.pop("request_timeout")

    resolved.update(merged)
    return resolved


#: Target config keys read into :class:`ModelSpec` fields; the rest are
#: adapter options and go to ``extra``.
_TARGET_SPEC_FIELDS = ("max_tokens", "temperature", "top_p", "timeout", "thinking")

#: Generation and provider options a target's metadata may carry.
_TARGET_METADATA_KEYS = (
    "api_key",
    "max_tokens",
    "temperature",
    "top_p",
    "top_k",
    "num_ctx",
    "stream",
    "timeout",
    "thinking",
    "tools",
    "tool_choice",
    "extra_body",
    "reasoning_effort",
)


def _target_spec(
    *,
    name: str,
    endpoint: str,
    agent_type: AgentType,
    metadata: Dict[str, Any],
    config: Dict[str, Any],
) -> ModelSpec:
    """Build the target's spec from the facade's metadata and adapter config.

    The model name is the config's ``name``, else the metadata's, else the
    agent name. ADK uses the agent name, which is its app name.
    """
    flat = {k: metadata[k] for k in _TARGET_METADATA_KEYS if k in metadata}
    flat.update({k: v for k, v in config.items() if v is not None})
    model_name = flat.pop("name", None) or metadata.get("name") or name
    if agent_type == AgentType.GOOGLE_ADK:
        model_name = name
    fields: Dict[str, Any] = {
        key: flat.pop(key) for key in _TARGET_SPEC_FIELDS if key in flat
    }
    return ModelSpec(
        identifier=str(model_name),
        endpoint=flat.pop("endpoint", None) or endpoint or None,
        agent_type=agent_type,
        api_key=flat.pop("api_key", None) or None,
        extra=flat,
        **fields,
    )


class HackAgent:
    """
    The primary client for orchestrating security assessments with HackAgent.

    This class serves as the main entry point to the HackAgent library, providing
    a high-level interface for:
    - Configuring victim agents that will be assessed.
    - Defining and selecting attack strategies.
    - Executing automated security tests against the configured agents.
    - Retrieving and handling test results.

    It registers the target as an Agent record in the storage backend,
    connects to it (applying any guardrails), and dispatches ``hack`` to
    :func:`hackagent.orchestrator.runner.run`.

    Attributes:
        target: The connected target model, with guardrails applied.
        agent_record: The target's Agent record in the storage backend.
        router: ``target`` behind the ``route_request`` surface the attack
            techniques call.
        models: Builds role models (attacker, judges, guardrails).
    """

    def __init__(
        self,
        endpoint: str,
        name: Optional[str] = None,
        agent_type: Union[AgentType, str] = AgentType.UNKNOWN,
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
        backend: Optional[Any] = None,
    ):
        """
        Initializes the HackAgent client and prepares it for interaction.

        This constructor sets up the local storage backend, loads default
        prompts, resolves the agent type, registers the target with the
        backend and connects to it.

        Args:
            endpoint: The target application's endpoint URL. This is the primary
                interface that the configured agent will interact with or represent
                during security tests.
            name: An optional descriptive name for the agent being configured.
                If not provided, a default name might be assigned or behavior might
                depend on the specific backend agent management policies.
            agent_type: Specifies the type of the agent. This can be provided
                as an `AgentType` member (e.g., `AgentType.GOOGLE_ADK`) or
                as a string identifier (e.g., "google-adk", "litellm").
                String values are automatically converted to the corresponding
                `AgentType` member. Defaults to `AgentType.UNKNOWN` if
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
            backend: Optional pre-built ``Store`` to persist runs and
                results through. When omitted, a backend is selected from the
                resolved API key (remote) or a default local SQLite database.
                Supplying one lets an embedding host — e.g. the local dashboard
                — reuse its own already-open backend.
        """

        self.settings = Settings.resolve(api_key=api_key, base_url=base_url)

        if backend is not None:
            self.backend = backend
            logger.info(
                "HackAgent using caller-provided backend %s", type(backend).__name__
            )
        elif self.settings.api_key:
            from hackagent.storage.remote import RemoteBackend

            self.backend = RemoteBackend.connect(
                self.settings.base_url,
                self.settings.api_key,
                timeout=timeout,
                raise_on_unexpected_status=raise_on_unexpected_status,
            )
            logger.info("HackAgent using remote backend → %s", self.settings.base_url)
        else:
            from hackagent.storage.local import LocalBackend

            self.backend = LocalBackend(db_path=self.settings.db_path)
            logger.info(
                "HackAgent using local backend → %s. Set HACKAGENT_API_KEY or "
                "pass api_key= to enable remote tracking.",
                self.settings.db_path,
            )

        processed_agent_type = AgentType.parse(agent_type)
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

        if processed_agent_type == AgentType.OLLAMA:
            if (
                thinking is not None
                and router_operational_config.get("thinking") is None
            ):
                router_operational_config["thinking"] = thinking
        else:
            # Keep `thinking` strictly OLLAMA-specific.
            router_operational_config.pop("thinking", None)

        check_supported(processed_agent_type)
        self.models = ModelFactory(self.settings)

        # The target is the only model registered as an Agent record.
        context = self.backend.get_context()
        self.organization_id = context.org_id
        if processed_agent_type == AgentType.GOOGLE_ADK:
            router_operational_config.setdefault("user_id", context.user_id)
        self.target_spec = _target_spec(
            name=name or endpoint,  # fall back to endpoint if no name provided
            endpoint=endpoint,
            agent_type=processed_agent_type,
            metadata=router_metadata,
            config=router_operational_config,
        )
        self.agent_record = self.backend.create_or_update_agent(
            name=name or endpoint,
            agent_type=processed_agent_type.value,
            endpoint=endpoint,
            metadata=router_metadata,
            overwrite_metadata=True,
        )
        self.agent_id = self.agent_record.id

        # Guardrails wrap the target once and apply to every call of every
        # attack on it.
        self.guardrails: Dict[str, GuardrailSpec] = {}
        for side, guardrail_config in (
            ("before", before_guardrail),
            ("after", after_guardrail),
        ):
            if guardrail_config:
                self.guardrails[side] = spec_from_config(
                    guardrail_config, spec_type=GuardrailSpec
                )
                logger.info("%s guardrail active on the target.", side)
        self.target: EnvelopeLLM = connect(
            self.target_spec, instance_id=str(self.agent_record.id)
        )
        if self.guardrails:
            self.target = Guarded(
                self.target,
                before=self._build_guardrail("before"),
                after=self._build_guardrail("after"),
            )
        self.router = LLMRouter(self.target, agent=self.agent_record)

    def _build_guardrail(self, side: str) -> Optional[LLMGuardrail]:
        spec = self.guardrails.get(side)
        if spec is None:
            return None
        return LLMGuardrail(
            self.models.for_role(spec), system_prompt=spec.system_prompt
        )

    def hack(
        self,
        attack_config: Dict[str, Any],
        run_config_override: Optional[Dict[str, Any]] = None,
        fail_on_run_error: bool = True,
        _tui_event_bus: Optional[Any] = None,
    ) -> Any:
        """
        Executes one attack against the configured victim agent.

        This method is the primary action for initiating an attack.
        ``attack_config`` must include ``attack_type``. Execution is
        delegated to :func:`hackagent.orchestrator.runner.run`.

        Args:
            attack_config: A dictionary containing parameters specific to the
                chosen attack type. Must include an 'attack_type' key that maps
                to a registered technique (e.g., "advprefix"). Other keys provide
                configuration for that technique.
            run_config_override: An optional dictionary that can override default
                run configurations. The specifics depend on the technique
                and backend capabilities.
            fail_on_run_error: If `True` (the default), an exception will be
                raised if the attack run encounters an error and fails. If `False`,
                errors might be suppressed or handled differently by the run.

        Returns:
            Result rows for the run. Each row is the dict produced by
            :func:`hackagent.orchestrator.mapping.result_to_row`.

        Raises:
            ValueError: If the 'attack_type' is missing from `attack_config` or
                if the specified 'attack_type' is not a supported/registered
                technique.
            HackAgentError: For issues during backend
                agent operations, or other unexpected errors during the attack process.
        """
        try:
            from hackagent.orchestrator.runner import run as run_attack

            attack_type = attack_config.get("attack_type")
            if not attack_type:
                raise ValueError("'attack_type' must be provided in attack_config.")

            backend_agent = self.agent_record
            logger.info(
                f"Preparing to attack agent '{backend_agent.name}' "
                f"(ID: {backend_agent.id}, Type: {backend_agent.agent_type}) "
                f"configured in this HackAgent instance, using strategy '{attack_type}'."
            )
            return run_attack(
                self,
                attack_config,
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
        ``_is_successful_result``): a goal
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
                ``hackagent.catalog.risks.jailbreak.JAILBREAK_PROFILE``). A goal
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
        from hackagent.orchestrator.chain import hack_chain as _hack_chain

        return _hack_chain(
            self,
            attacks=attacks,
            goals=goals,
            run_config_override=run_config_override,
            fail_on_run_error=fail_on_run_error,
            escalate_only_mitigated=escalate_only_mitigated,
            _tui_event_bus=_tui_event_bus,
        )
