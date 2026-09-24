# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
h4rm3l attack implementation.

Composable prompt-decoration attack that chains multiple text transformations
(encoding, obfuscation, roleplaying, persuasion) to bypass LLM safety filters.

Based on: Doumbouya et al., "h4rm3l: A Dynamic Benchmark of Composable
Jailbreak Attacks for LLM Safety Assessment" (2024)
https://arxiv.org/abs/2408.04811

The attack works by applying a user-defined "program" — a chain of
PromptDecorator transforms — to each goal prompt before sending it to
the target model.  Decorators range from simple text manipulations
(base64, character corruption) to LLM-assisted rewrites (translation,
persuasion, persona injection).
"""

import copy
import logging
from typing import Any, Dict, List, Optional

from hackagent.attacks._lib.legacy_seams import Store
from hackagent.attacks._lib.llm_router import LLMRouter
from hackagent.attacks.ports import RunContext
from hackagent.attacks.techniques.base import BaseAttack
from hackagent.attacks.types import AttackResult, rows_to_attack_results


from . import generation
from .config import DEFAULT_H4RM3L_CONFIG, PRESET_PROGRAMS
from hackagent.attacks.techniques.h4rm3l.config import H4rm3lConfig


def _recursive_update(target_dict, source_dict):
    """Recursively merge source into target, deep-copying non-internal values."""
    for key, source_value in source_dict.items():
        target_value = target_dict.get(key)
        if isinstance(source_value, dict) and isinstance(target_value, dict):
            _recursive_update(target_value, source_value)
        elif key.startswith("_"):
            target_dict[key] = source_value
        else:
            target_dict[key] = copy.deepcopy(source_value)


def _emit_h4rm3l_decoration_traces(input_data, *, events=None, tracker=None):
    """Emit decoration step traces via Events (preferred) or legacy tracker."""
    for idx, item in enumerate(input_data or []):
        goal_text = item.get("goal", "")
        for step in item.get("decoration_steps", []) or []:
            step_index = step.get("step_index")
            decorator_name = step.get("decorator", "UnknownDecorator")
            payload = {
                "step_name": f"Decoration Step {step_index}",
                "decorator": decorator_name,
                "input_prompt": step.get("input_prompt", ""),
                "decoration_applied": decorator_name,
                "decorated_prompt": step.get("decorated_prompt", ""),
                "input_length": step.get("input_length"),
                "output_length": step.get("output_length"),
                "length_delta": step.get("length_delta"),
                "content_changed": step.get("content_changed"),
                "uses_decorator_llm": step.get("uses_decorator_llm", False),
                "decorator_llm_identifier": step.get("decorator_llm_identifier"),
                "decorator_llm_endpoint": step.get("decorator_llm_endpoint"),
                "decorator_llm_prompt": step.get("decorator_llm_prompt"),
                "decorator_llm_response": step.get("decorator_llm_response"),
                "goal": goal_text,
            }
            if events is not None:
                events.trace(**payload)
                continue
            if tracker is None:
                continue
            goal_ctx = (
                tracker.get_goal_context_by_goal(goal_text)
                if goal_text
                else tracker.get_goal_context(idx)
            )
            if not goal_ctx:
                continue
            tracker.add_custom_trace(
                ctx=goal_ctx,
                step_name=f"Decoration Step {step_index}: {decorator_name}",
                content=payload,
            )


def _h4rm3l_decoration_hook(input_data, raw_config):
    """Legacy pre-eval hook retained for callers that still pass it."""
    _emit_h4rm3l_decoration_traces(
        input_data,
        tracker=raw_config.get("_tracker") if isinstance(raw_config, dict) else None,
    )


class H4rm3lAttack(BaseAttack):
    """
    h4rm3l — composable prompt-decoration jailbreak attack.

    Applies a chain of PromptDecorator transforms to each goal prompt
    and sends the decorated prompt to the target model. The embedded
    judge step is gone. ``run()`` returns rows without a verdict.
    Decoration traces go to ``ctx.events.trace`` when ``ctx`` is set
    (the legacy tracker remains the fallback). Generation can take an
    explicit ``decorator_llm_router``.

    Construct with ``(config, ctx)``. ``config`` is a dict deep-merged
    into the h4rm3l defaults. ``ctx`` is a
    :class:`~hackagent.attacks.ports.RunContext`, passed positionally or
    as ``ctx=``. Tests build it with ``make_ctx()``
    (``tests.fakes.context``). The legacy constructor
    ``(config_dict, client, agent_router)`` is obsolete for new code.
    :class:`~hackagent.attacks.techniques.h4rm3l.config.H4rm3lConfig`
    still subclasses :class:`~hackagent.attacks.techniques.config.ConfigBase`.

    Pipeline:
        1. **Generation** — Compile the decorator program, apply to each
           goal in parallel, query the target model.

    The decorator program is specified via ``h4rm3l_params.program``.
    It can be:
        - A preset name from :data:`PRESET_PROGRAMS` (e.g.
          ``"base64_refusal_suppression"``)
        - A raw program string in v1 or v2 syntax (e.g.
          ``"Base64Decorator().then(RefusalSuppressionDecorator())"``).

    Attributes:
        program: The resolved decorator program string.
        syntax_version: Program syntax version (1 or 2).
    """

    config_model = H4rm3lConfig

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        ctx_or_client: Any = None,
        agent_router: Optional[LLMRouter] = None,
        *,
        ctx: Optional[RunContext] = None,
        client: Optional[Store] = None,
    ):
        if ctx is None and isinstance(ctx_or_client, RunContext):
            ctx = ctx_or_client
        resolved_client = (
            client
            if client is not None
            else (None if isinstance(ctx_or_client, RunContext) else ctx_or_client)
        )
        if ctx is None:
            if resolved_client is None:
                raise ValueError("A storage backend must be provided")
            if agent_router is None:
                raise ValueError("LLMRouter must be provided")
            client = resolved_client

        current_config = copy.deepcopy(DEFAULT_H4RM3L_CONFIG)
        if config:
            _recursive_update(current_config, config)

        self.logger = logging.getLogger("hackagent.attacks.h4rm3l")
        if ctx is not None:
            super().__init__(current_config, ctx)
        else:
            super().__init__(current_config, client, agent_router)

    def _setup(self) -> None:
        """Standard setup plus h4rm3l-specific initialisation."""
        super()._setup()
        params = self.config.get("h4rm3l_params", {})
        self.program = params.get("program", "IdentityDecorator()")
        self.syntax_version = params.get("syntax_version", 2)

        # Resolve preset name
        if self.program in PRESET_PROGRAMS:
            self.logger.info(f"Resolved preset program: {self.program}")
        else:
            self.logger.info(
                f"Using custom program (v{self.syntax_version}): {self.program[:80]}..."
            )

    def _validate_config(self):
        super()._validate_config()
        required_keys = ["attack_type", "h4rm3l_params"]
        missing = [k for k in required_keys if k not in self.config]
        if missing:
            raise ValueError(f"Missing required config keys: {', '.join(missing)}")

        params = self.config.get("h4rm3l_params", {})
        if not params:
            raise ValueError("h4rm3l_params must be a non-empty dict")

        syntax_version = params.get("syntax_version", 2)
        if syntax_version not in (1, 2):
            raise ValueError(f"syntax_version must be 1 or 2, got {syntax_version}")

    def _get_pipeline_steps(self) -> List[Dict]:
        """Define the two-stage attack pipeline."""
        return [
            {
                "name": "Generation: Apply h4rm3l Decorators and Query Target",
                "function": generation.execute,
                "step_type_enum": "GENERATION",
                "config_keys": [
                    "h4rm3l_params",
                    "decorator_llm",
                    "_run_id",
                    "_backend",
                    "_client",
                    "_tracker",
                ],
                "input_data_arg_name": "goals",
                "required_args": ["logger", "agent_router", "config"],
            }
        ]

    def run(self, goals: Optional[List[str]] = None, **kwargs) -> List[AttackResult]:
        """
        Execute the full h4rm3l attack pipeline.

        Args:
            goals: List of goal strings to attack.

        Returns:
            List of result dicts with evaluation scores, or ``[]`` if
            no goals provided.
        """
        goals = goals or []
        if not goals:
            return []

        # Create coordinator (deferred goal-result creation)
        coordinator = self._initialize_coordinator(attack_type="h4rm3l")

        pipeline_steps = self._get_pipeline_steps()
        start_step = self.config.get("start_step", 1) - 1

        # Initialize goal results and tracker BEFORE generation so that
        # generation.execute() can record per-goal interaction traces.
        h4rm3l_params = self.config.get("h4rm3l_params", {})
        goal_metadata = {
            "attack_type": "h4rm3l",
            "program": h4rm3l_params.get("program", ""),
            "syntax_version": h4rm3l_params.get("syntax_version", 2),
        }
        coordinator.initialize_goals(goals, initial_metadata=goal_metadata)
        if coordinator.goal_tracker:
            self.config["_tracker"] = coordinator.goal_tracker

        if coordinator.has_goal_tracking:
            self.logger.info("Using TrackingCoordinator for per-goal tracking")

        try:
            results = self._execute_pipeline(
                pipeline_steps, goals, start_step=start_step
            )

            if not results:
                self.logger.warning("Generation produced no output")
                coordinator.finalize_pipeline([], lambda _: False)
                return []

            events = self.ctx.events if self.ctx is not None else None
            tracker = coordinator.goal_tracker
            _emit_h4rm3l_decoration_traces(results, events=events, tracker=tracker)

            coordinator.finalize_all_goals(results)
            coordinator.log_summary()
            coordinator.finalize_pipeline(results)
            return rows_to_attack_results(results)

        except Exception:
            coordinator.finalize_on_error("h4rm3l pipeline failed with exception")
            raise
