# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
h4rm3l generation and execution module.

Compiles the decorator program, applies it to each goal prompt, and
sends the decorated prompt to the target model via AgentRouter.
"""

import logging
import time
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

from hackagent.router.router import AgentRouter

from .config import PRESET_PROGRAMS
from .decorators import (
    compile_program_with_steps,
    has_prompting_interface,
    is_llm_assisted_decorator_name,
    set_prompting_interface,
)

if TYPE_CHECKING:
    from hackagent.router.tracking import Tracker


def _build_prompting_interface(
    config: Dict[str, Any], agent_router: AgentRouter
) -> Optional[Callable]:
    """Build an LLM prompting function for LLM-assisted decorators.

    Uses the ``decorator_llm`` config or falls back to the target model.

    Returns:
        A callable ``(prompt, maxtokens, temperature) -> str``, or ``None``.
    """
    decorator_llm = config.get("decorator_llm", {})
    identifier = decorator_llm.get("identifier")
    endpoint = decorator_llm.get("endpoint")
    api_key = decorator_llm.get("api_key")
    agent_type = decorator_llm.get("agent_type", "OPENAI_SDK")

    # If decorator_llm has valid config, create a separate router
    if identifier and api_key:
        try:
            from hackagent.router.router import AgentRouter as AR

            llm_router = AR.create_for_config(
                identifier=identifier,
                endpoint=endpoint,
                agent_type=agent_type,
                api_key=api_key,
            )
            llm_key = str(llm_router.backend_agent.id)

            def _prompt(
                prompt_text: str, maxtokens: int = 500, temperature: float = 1.0
            ) -> str:
                resp = llm_router.route_request(
                    registration_key=llm_key,
                    request_data={"prompt": prompt_text},
                )
                return resp.get("generated_text", "")

            _prompt._llm_identifier = identifier
            _prompt._llm_endpoint = endpoint
            _prompt._llm_agent_type = str(agent_type)
            _prompt._llm_role = "decorator_llm"

            return _prompt
        except Exception:
            pass

    # Fallback: use the target model itself
    victim_key = str(agent_router.backend_agent.id)

    def _prompt_via_target(
        prompt_text: str, maxtokens: int = 500, temperature: float = 1.0
    ) -> str:
        resp = agent_router.route_request(
            registration_key=victim_key,
            request_data={"prompt": prompt_text},
        )
        return resp.get("generated_text", "")

    fallback_identifier = (
        config.get("model")
        or config.get("target_model")
        or getattr(agent_router.backend_agent, "name", None)
        or getattr(agent_router.backend_agent, "model", None)
        or getattr(agent_router.backend_agent, "id", "target_model")
    )
    _prompt_via_target._llm_identifier = str(fallback_identifier)
    _prompt_via_target._llm_endpoint = getattr(
        agent_router.backend_agent, "endpoint", None
    )
    _prompt_via_target._llm_agent_type = "TARGET_FALLBACK"
    _prompt_via_target._llm_role = "target_fallback"

    return _prompt_via_target


def execute(
    goals: List[str],
    agent_router: AgentRouter,
    config: Dict[str, Any],
    logger: logging.Logger,
) -> List[Dict]:
    """
    Generate decorated prompts and execute them against the target model.

    Args:
        goals: List of goal strings to attack.
        agent_router: Router for target model communication.
        config: Configuration dictionary with ``h4rm3l_params``.
        logger: Logger instance.

    Returns:
        List of result dicts with goal, decorated prompt, and response.
    """
    params = config.get("h4rm3l_params", {})
    program_str = params.get("program", "IdentityDecorator()")
    syntax_version = params.get("syntax_version", 2)

    if "synthesis_model" in params:
        logger.warning(
            "h4rm3l_params.synthesis_model is deprecated and ignored; "
            "use decorator_llm.identifier instead."
        )

    tracker: Optional["Tracker"] = config.get("_tracker")

    # Resolve preset program names
    if program_str in PRESET_PROGRAMS:
        resolved_program = PRESET_PROGRAMS[program_str]
        logger.info(f"Using preset program '{program_str}': {resolved_program[:80]}...")
    else:
        resolved_program = program_str
        logger.info(f"Using custom program: {resolved_program[:80]}...")

    # Set up LLM-assisted decorators if needed
    llm_keywords = [
        "TranslateDecorator",
        "PAPDecorator",
        "PersonaDecorator",
        "PersuasiveDecorator",
        "SynonymDecorator",
        "ResearcherDecorator",
        "VillainDecorator",
        "VisualObfuscationDecorator",
        "TransformFxDecorator",
    ]
    needs_llm = any(kw in resolved_program for kw in llm_keywords)
    decoration_llm_identifier = None
    decoration_llm_endpoint = None

    if needs_llm:
        prompting_fn = _build_prompting_interface(config, agent_router)
        if prompting_fn:
            set_prompting_interface(prompting_fn)
            decoration_llm_identifier = getattr(prompting_fn, "_llm_identifier", None)
            decoration_llm_endpoint = getattr(prompting_fn, "_llm_endpoint", None)
            logger.info("LLM prompting interface configured for assistive decorators")
        else:
            logger.warning(
                "Program uses LLM-assisted decorators but no prompting "
                "interface could be set up. These decorators may fail."
            )

    # Compile the decorator chain
    try:
        _decorator_fn, decorator_steps = compile_program_with_steps(
            resolved_program,
            syntax_version,
        )
    except Exception as e:
        logger.error(f"Failed to compile h4rm3l program: {e}")
        return [
            {"goal": g, "error": f"Program compilation failed: {e}", "response": None}
            for g in goals
        ]

    logger.info(f"Compiled decorator chain (syntax v{syntax_version})")
    logger.info(f"Processing {len(goals)} goal(s)")

    victim_key = str(agent_router.backend_agent.id)
    results_map: Dict[int, Dict[str, Any]] = {}

    def _process_goal(idx: int, goal_text: str) -> None:
        _t0 = time.perf_counter()
        _label = f"Goal {idx + 1}/{len(goals)}"

        # Step 1: Decorate the prompt (with per-step trace)
        try:
            current_prompt = goal_text
            decoration_traces: List[Dict[str, Any]] = []

            for step_idx, decorator in enumerate(decorator_steps, start=1):
                decorator_name = decorator.__class__.__name__
                input_prompt = current_prompt
                if hasattr(decorator, "_last_llm_prompt"):
                    decorator._last_llm_prompt = None
                if hasattr(decorator, "_last_llm_response"):
                    decorator._last_llm_response = None
                output_prompt = decorator.decorate(input_prompt)

                uses_decorator_llm = is_llm_assisted_decorator_name(decorator_name)
                if uses_decorator_llm and has_prompting_interface():
                    llm_identifier = decoration_llm_identifier
                    llm_endpoint = decoration_llm_endpoint
                else:
                    llm_identifier = None
                    llm_endpoint = None

                input_len = len(input_prompt)
                output_len = len(output_prompt)

                step_trace = {
                    "step_index": step_idx,
                    "decorator": decorator_name,
                    "input_prompt": input_prompt,
                    "decorated_prompt": output_prompt,
                    "input_length": input_len,
                    "output_length": output_len,
                    "length_delta": output_len - input_len,
                    "content_changed": output_prompt != input_prompt,
                    "uses_decorator_llm": uses_decorator_llm,
                    "decorator_llm_identifier": llm_identifier,
                    "decorator_llm_endpoint": llm_endpoint,
                    "decorator_llm_prompt": getattr(
                        decorator, "_last_llm_prompt", None
                    ),
                    "decorator_llm_response": getattr(
                        decorator, "_last_llm_response", None
                    ),
                }
                decoration_traces.append(step_trace)

                logger.info(
                    "[%s][Decoration Step %d] decorator=%s uses_llm=%s llm=%s",
                    _label,
                    step_idx,
                    decorator_name,
                    uses_decorator_llm,
                    llm_identifier or "n/a",
                )
                logger.info(
                    "[%s][Decoration Step %d] input (len=%d):\n%s",
                    _label,
                    step_idx,
                    len(input_prompt),
                    input_prompt,
                )
                logger.info(
                    "[%s][Decoration Step %d] output (len=%d):\n%s",
                    _label,
                    step_idx,
                    output_len,
                    output_prompt,
                )

                current_prompt = output_prompt

            decorated_prompt = current_prompt
        except Exception as e:
            logger.error(f"[{_label}] Decoration failed: {e}")
            results_map[idx] = {
                "goal": goal_text,
                "program": resolved_program,
                "decoration_steps": [],
                "full_prompt": None,
                "error": f"Decoration failed: {e}",
                "response": None,
            }
            return

        # Log the decorated prompt (full)
        logger.info(
            "[%s] Full prompt (len=%d):\n%s",
            _label,
            len(decorated_prompt),
            decorated_prompt,
        )

        # Step 2: Send to target model
        request_data = {"prompt": decorated_prompt}
        try:
            response = agent_router.route_request(
                registration_key=victim_key,
                request_data=request_data,
            )
        except Exception as e:
            logger.error(f"[{_label}] Target execution failed: {e}")
            results_map[idx] = {
                "goal": goal_text,
                "program": resolved_program,
                "decoration_steps": decoration_traces,
                "full_prompt": decorated_prompt,
                "error": f"Execution failed: {e}",
                "response": None,
            }
            return

        generated_text = response.get("generated_text")
        error_message = response.get("error_message")

        # Log the response (full)
        if generated_text:
            logger.info(
                "[%s] Full response (len=%d):\n%s",
                _label,
                len(generated_text),
                generated_text,
            )
        else:
            logger.info(f"[{_label}] No response (error={error_message})")

        _elapsed = round(time.perf_counter() - _t0, 3)

        # Add trace to Tracker
        if tracker:
            goal_ctx = tracker.get_goal_context(idx)
            if goal_ctx:
                tracker.add_interaction_trace(
                    ctx=goal_ctx,
                    request=request_data,
                    response={
                        "generated_text": generated_text,
                        "error_message": error_message,
                    },
                    step_name="h4rm3l Generation",
                    metadata={
                        "program": resolved_program,
                        "original_goal": goal_text,
                        "elapsed_s": _elapsed,
                    },
                )

        results_map[idx] = {
            "goal": goal_text,
            "program": resolved_program,
            "decoration_steps": decoration_traces,
            "full_prompt": decorated_prompt,
            "response": generated_text,
            "error": error_message,
            "elapsed_s": _elapsed,
        }

    for idx, goal_text in enumerate(goals):
        _process_goal(idx, goal_text)

    ordered = [results_map[i] for i in range(len(goals))]

    # Summary
    ok_count = sum(1 for r in ordered if r.get("response"))
    err_count = sum(1 for r in ordered if r.get("error"))
    logger.info(f"Generation complete: {ok_count} responses, {err_count} errors")

    return ordered
