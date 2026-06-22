# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
FC-Attack generation and execution module.

Provides two entry points:

- ``execute_fc`` — Renders flowchart images and sends them to a VLM.
- ``execute_tfc`` — Serializes flowcharts as text and sends to any LLM.

Shared logic (step decomposition, target execution, result recording) is
factored into private helpers.

Based on: Zhang et al., "FC-Attack: Jailbreaking Multimodal Large
Language Models via Auto-Generated Flowcharts" (EMNLP 2025 Findings)
"""

import logging
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from hackagent.router.router import AgentRouter

from .flowchart_renderer import (
    TEXT_FORMAT_SERIALIZERS,
    render_flowchart,
)
from .prompts import FEW_SHOT_STEP_DECOMPOSITION, SYSTEM_PROMPT, USER_PROMPT

if TYPE_CHECKING:
    from hackagent.router.tracking import Tracker


# ─── Step Decomposition ──────────────────────────────────────────────────────


def _decompose_goal_to_steps(goal: str, num_steps: int) -> List[str]:
    """
    Decompose a goal into step descriptions using a simple heuristic.

    Splits the goal into actionable sub-instructions.
    """
    sentences = re.split(r"[.;]\s*", goal.strip())
    sentences = [s.strip() for s in sentences if s.strip()]

    if len(sentences) >= num_steps:
        return sentences[:num_steps]

    words = goal.split()
    if len(words) <= 3:
        steps = [
            f"Understand the task: {goal}",
            f"Research methods for: {goal}",
            "Gather required materials",
            "Execute the plan step by step",
            f"Verify completion of: {goal}",
        ]
        return steps[:num_steps]

    steps = []
    chunk_size = max(1, len(words) // num_steps)
    for i in range(num_steps):
        start = i * chunk_size
        end = start + chunk_size if i < num_steps - 1 else len(words)
        chunk = " ".join(words[start:end])
        if chunk:
            steps.append(chunk)

    while len(steps) < num_steps:
        steps.append("Continue with remaining details...")

    return steps[:num_steps]


def _parse_steps_from_response(response_text: str, num_steps: int) -> List[str]:
    """Parse numbered steps from an LLM response."""
    lines = response_text.strip().split("\n")
    steps = []
    for line in lines:
        line = line.strip()
        match = re.match(r"^\d+[.)]\s*(.+)$", line)
        if match:
            steps.append(match.group(1).strip())
        elif line and not line.startswith("#"):
            steps.append(line)

    if not steps:
        return _decompose_goal_to_steps(response_text, num_steps)

    return steps[:num_steps]


def _create_step_generator_router(
    agent_router: AgentRouter,
    config: Dict[str, Any],
    logger: logging.Logger,
) -> Optional[tuple]:
    """
    Create a step-generator router if configured.

    Returns a (router, registration_key, step_generator_config) tuple,
    or None if no step generator is configured.
    """
    step_generator = config.get("step_generator")

    if not step_generator or not isinstance(step_generator, dict):
        return None

    generator_model = step_generator.get("identifier")
    if not generator_model:
        return None

    from hackagent.attacks.shared.router_factory import create_router

    generator_config = {
        "identifier": generator_model,
        "endpoint": step_generator.get("endpoint"),
        "agent_type": step_generator.get("agent_type", "OPENAI_SDK"),
        "api_key": step_generator.get("api_key"),
        "max_tokens": int(step_generator.get("max_tokens", 512)),
        "temperature": float(step_generator.get("temperature", 0.3)),
    }
    router, reg_key = create_router(
        backend=agent_router.backend,
        config=generator_config,
        logger=logger,
        router_name="fc_step_generator",
    )
    return router, reg_key, step_generator


def _generate_steps_with_model(
    goal: str,
    num_steps: int,
    generator_router: AgentRouter,
    gen_key: str,
    step_generator: Dict[str, Any],
    logger: logging.Logger,
) -> Optional[List[str]]:
    """Generate steps using a pre-created step generator router."""
    try:
        prompt = FEW_SHOT_STEP_DECOMPOSITION.format(goal=goal)
        max_tokens = int(step_generator.get("max_tokens", 512))
        temperature = float(step_generator.get("temperature", 0.3))

        response = generator_router.route_request(
            registration_key=gen_key,
            request_data={
                "prompt": prompt,
                "max_tokens": max_tokens,
                "temperature": temperature,
            },
        )
        generated_text = response.get("generated_text", "")
        if generated_text:
            return _parse_steps_from_response(generated_text, num_steps)
    except Exception as e:
        logger.warning(f"Step generator model failed, using fallback: {e}")

    return None


def _get_steps(
    goal_text: str,
    num_steps: int,
    truncate_last_step: bool,
    gen_router_info: Optional[tuple],
    logger: logging.Logger,
) -> List[str]:
    """Decompose goal into steps and optionally truncate the last one."""
    steps: Optional[List[str]] = None
    if gen_router_info:
        gen_router, gen_key, step_gen_cfg = gen_router_info
        steps = _generate_steps_with_model(
            goal_text, num_steps, gen_router, gen_key, step_gen_cfg, logger
        )
    if steps is None:
        steps = _decompose_goal_to_steps(goal_text, num_steps)

    if truncate_last_step and steps:
        last_step = steps[-1]
        truncation_point = max(3, len(last_step) * 3 // 5)
        steps[-1] = last_step[:truncation_point] + "..."

    return steps


# ─── Message Building ─────────────────────────────────────────────────────────

_LANG_HINTS = {
    "dot": "dot",
    "mermaid": "mermaid",
    "tikz": "latex",
    "plantuml": "plantuml",
    "ascii": "",
}


def _build_multimodal_messages(
    image_data_url: str,
    system_prompt: str,
    user_prompt: str,
) -> List[Dict[str, Any]]:
    """Build OpenAI-compatible multimodal message list with system + user."""
    messages: List[Dict[str, Any]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append(
        {
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": image_data_url}},
                {"type": "text", "text": user_prompt},
            ],
        }
    )
    return messages


def _build_text_only_prompt(graph_text: str, text_format: str) -> str:
    """Build the full user prompt string with embedded graph text."""
    lang = _LANG_HINTS.get(text_format, text_format)
    return f"{USER_PROMPT}\n\n```{lang}\n{graph_text}\n```"


def _build_text_only_messages(
    graph_text: str,
    text_format: str,
    system_prompt: str,
) -> List[Dict[str, Any]]:
    """Build text-only messages embedding the flowchart graph description."""
    combined_user = _build_text_only_prompt(graph_text, text_format)

    messages: List[Dict[str, Any]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": combined_user})
    return messages


# ─── Target Execution ─────────────────────────────────────────────────────────


def _send_to_target(
    messages: List[Dict[str, Any]],
    agent_router: AgentRouter,
    victim_key: str,
    config: Dict[str, Any],
    logger: logging.Logger,
    goal_idx: int,
    total_goals: int,
) -> Tuple[Optional[str], Optional[str], float]:
    """
    Send messages to the target model.

    Returns:
        (generated_text, error_message, elapsed_seconds)
    """
    request_data: Dict[str, Any] = {"messages": messages}
    max_tokens = config.get("max_tokens")
    if max_tokens is not None:
        request_data["max_tokens"] = max_tokens

    _t0 = time.perf_counter()
    logger.info(f"[Goal {goal_idx}/{total_goals}] Sending flowchart to target model")

    response = agent_router.route_request(
        registration_key=victim_key,
        request_data=request_data,
    )

    elapsed = round(time.perf_counter() - _t0, 3)
    generated_text = response.get("generated_text")
    error_message = response.get("error_message")

    if generated_text:
        logger.info(
            f"[Goal {goal_idx}/{total_goals}] Target responded in {elapsed}s: "
            f"{generated_text[:200]}..."
        )
    elif error_message:
        logger.warning(f"[Goal {goal_idx}/{total_goals}] Target error: {error_message}")

    return generated_text, error_message, elapsed


# ─── FC-Attack (Image/Multimodal) ────────────────────────────────────────────


def execute_fc(
    goals: List[str],
    agent_router: AgentRouter,
    config: Dict[str, Any],
    logger: logging.Logger,
) -> List[Dict[str, Any]]:
    """
    FC-Attack: render flowchart images and send to a Vision-Language Model.

    Pipeline:
    1. Decompose each goal into numbered steps.
    2. Optionally truncate the last step to induce completion.
    3. Render steps as a flowchart image (vertical/horizontal/tortuous).
    4. Send the image + jailbreak text prompt to the target VLM.

    Args:
        goals: List of harmful prompts to encode as flowcharts.
        agent_router: Router for target model communication.
        config: Configuration dictionary with ``fc_params``.
        logger: Logger instance.

    Returns:
        List of result dicts compatible with the evaluation step.
    """
    params = config.get("fc_params", {})
    layout = params.get("layout", "vertical")
    dpi = params.get("dpi", 600)
    num_steps = params.get("num_steps", 6)
    truncate_last_step = params.get("truncate_last_step", True)

    tracker: Optional["Tracker"] = config.get("_tracker")
    logger.info(f"Initializing FC-Attack with layout={layout}, num_steps={num_steps}")

    victim_key = str(agent_router.backend_agent.id)
    batch_size = max(1, config.get("batch_size", 16))
    gen_router_info = _create_step_generator_router(agent_router, config, logger)

    _lock = threading.Lock()
    results_map: Dict[int, Dict[str, Any]] = {}

    def _process_goal(idx_goal: tuple) -> None:
        idx, goal_text = idx_goal
        _t0 = time.perf_counter()
        logger.info(f"Processing goal {idx + 1}/{len(goals)}")

        steps = _get_steps(
            goal_text, num_steps, truncate_last_step, gen_router_info, logger
        )

        # Render flowchart image
        try:
            render_result = render_flowchart(
                steps=steps,
                goal_text=goal_text,
                layout=layout,
                dpi=dpi,
            )
        except Exception as e:
            logger.error(f"Flowchart rendering failed for goal {idx + 1}: {e}")
            with _lock:
                results_map[idx] = {
                    "goal": goal_text,
                    "layout": layout,
                    "steps": steps,
                    "error": f"Rendering failed: {str(e)}",
                    "response": None,
                }
            return

        image_data_url = render_result["image_data_url"]

        # Build multimodal messages
        messages = _build_multimodal_messages(
            image_data_url=image_data_url,
            system_prompt=SYSTEM_PROMPT,
            user_prompt=USER_PROMPT,
        )
        full_prompt = USER_PROMPT

        logger.info(
            f"[Goal {idx + 1}/{len(goals)}] Rendered flowchart "
            f"(layout={layout}, steps={len(steps)})"
        )

        # Send to target
        try:
            generated_text, error_message, _req_elapsed = _send_to_target(
                messages,
                agent_router,
                victim_key,
                config,
                logger,
                idx + 1,
                len(goals),
            )
        except Exception as e:
            logger.error(f"Execution failed for goal {idx + 1}: {e}")
            with _lock:
                results_map[idx] = {
                    "goal": goal_text,
                    "layout": layout,
                    "steps": steps,
                    "text_prompt": USER_PROMPT,
                    "error": f"Execution failed: {str(e)}",
                    "response": None,
                }
            return

        # Record results
        with _lock:
            _goal_elapsed = round(time.perf_counter() - _t0, 3)

            _result_id = None
            if tracker:
                goal_ctx = tracker.get_goal_context_by_goal(goal_text)
                if goal_ctx:
                    _result_id = goal_ctx.result_id
                    tracker.add_interaction_trace(
                        ctx=goal_ctx,
                        request={
                            "prompt": USER_PROMPT,
                            "layout": layout,
                            "steps": steps,
                        },
                        response={
                            "generated_text": generated_text,
                            "error_message": error_message,
                        },
                        step_name=f"FC-Attack Generation ({layout})",
                        metadata={
                            "layout": layout,
                            "num_steps": len(steps),
                            "steps": steps,
                            "text_prompt": USER_PROMPT,
                            "full_prompt": full_prompt,
                            "image_data_url": image_data_url,
                            "elapsed_s": _goal_elapsed,
                        },
                    )

            result_entry: Dict[str, Any] = {
                "goal": goal_text,
                "layout": layout,
                "steps": steps,
                "text_prompt": USER_PROMPT,
                "full_prompt": full_prompt,
                "image_data_url": image_data_url,
                "response": generated_text,
                "error": error_message,
                "generation_elapsed_s": _goal_elapsed,
            }
            if _result_id:
                result_entry["result_id"] = _result_id
            results_map[idx] = result_entry

    with ThreadPoolExecutor(max_workers=batch_size) as pool:
        list(pool.map(_process_goal, enumerate(goals)))

    return [results_map[i] for i in range(len(goals))]


# ─── tFC-Attack (Text-only) ──────────────────────────────────────────────────


def execute_tfc(
    goals: List[str],
    agent_router: AgentRouter,
    config: Dict[str, Any],
    logger: logging.Logger,
) -> List[Dict[str, Any]]:
    """
    tFC-Attack: serialize flowcharts as text and send to any LLM.

    Pipeline:
    1. Decompose each goal into numbered steps.
    2. Optionally truncate the last step to induce completion.
    3. Serialize steps in the configured text format (ascii, mermaid, etc.).
    4. Send the text flowchart + jailbreak prompt to the target LLM.

    Args:
        goals: List of harmful prompts to encode as flowcharts.
        agent_router: Router for target model communication.
        config: Configuration dictionary with ``tfc_params``.
        logger: Logger instance.

    Returns:
        List of result dicts compatible with the evaluation step.
    """
    params = config.get("tfc_params", {})
    layout = params.get("layout", "vertical")
    text_format = params.get("text_format", "dot")
    num_steps = params.get("num_steps", 6)
    truncate_last_step = params.get("truncate_last_step", True)

    tracker: Optional["Tracker"] = config.get("_tracker")
    logger.info(
        f"Initializing tFC-Attack with layout={layout}, "
        f"text_format={text_format}, num_steps={num_steps}"
    )

    victim_key = str(agent_router.backend_agent.id)
    batch_size = max(1, config.get("batch_size", 16))
    gen_router_info = _create_step_generator_router(agent_router, config, logger)

    _lock = threading.Lock()
    results_map: Dict[int, Dict[str, Any]] = {}

    def _process_goal(idx_goal: tuple) -> None:
        idx, goal_text = idx_goal
        _t0 = time.perf_counter()
        logger.info(f"Processing goal {idx + 1}/{len(goals)}")

        steps = _get_steps(
            goal_text, num_steps, truncate_last_step, gen_router_info, logger
        )

        # Generate graph text in the configured format
        serializer_fn = TEXT_FORMAT_SERIALIZERS.get(text_format)
        if serializer_fn is None:
            logger.error(f"Unknown text_format: {text_format}, falling back to dot")
            serializer_fn = TEXT_FORMAT_SERIALIZERS["dot"]
        graph_text = serializer_fn(goal_text, steps, layout)

        # Build text-only messages
        full_prompt = _build_text_only_prompt(graph_text, text_format)
        messages = _build_text_only_messages(
            graph_text=graph_text,
            text_format=text_format,
            system_prompt=SYSTEM_PROMPT,
        )

        logger.info(
            f"[Goal {idx + 1}/{len(goals)}] Serialized flowchart "
            f"(layout={layout}, format={text_format}, steps={len(steps)})"
        )

        # Send to target
        try:
            generated_text, error_message, _req_elapsed = _send_to_target(
                messages,
                agent_router,
                victim_key,
                config,
                logger,
                idx + 1,
                len(goals),
            )
        except Exception as e:
            logger.error(f"Execution failed for goal {idx + 1}: {e}")
            with _lock:
                results_map[idx] = {
                    "goal": goal_text,
                    "layout": layout,
                    "steps": steps,
                    "text_prompt": USER_PROMPT,
                    "error": f"Execution failed: {str(e)}",
                    "response": None,
                }
            return

        # Record results
        with _lock:
            _goal_elapsed = round(time.perf_counter() - _t0, 3)

            _result_id = None
            if tracker:
                goal_ctx = tracker.get_goal_context_by_goal(goal_text)
                if goal_ctx:
                    _result_id = goal_ctx.result_id
                    tracker.add_interaction_trace(
                        ctx=goal_ctx,
                        request={
                            "prompt": USER_PROMPT,
                            "layout": layout,
                            "steps": steps,
                        },
                        response={
                            "generated_text": generated_text,
                            "error_message": error_message,
                        },
                        step_name=f"tFC-Attack Generation ({layout})",
                        metadata={
                            "layout": layout,
                            "num_steps": len(steps),
                            "steps": steps,
                            "text_prompt": USER_PROMPT,
                            "full_prompt": full_prompt,
                            "graph_text": graph_text,
                            "text_format": text_format,
                            "elapsed_s": _goal_elapsed,
                        },
                    )

            result_entry: Dict[str, Any] = {
                "goal": goal_text,
                "layout": layout,
                "steps": steps,
                "text_prompt": USER_PROMPT,
                "full_prompt": full_prompt,
                "graph_text": graph_text,
                "text_format": text_format,
                "response": generated_text,
                "error": error_message,
                "generation_elapsed_s": _goal_elapsed,
            }
            if _result_id:
                result_entry["result_id"] = _result_id
            results_map[idx] = result_entry

    with ThreadPoolExecutor(max_workers=batch_size) as pool:
        list(pool.map(_process_goal, enumerate(goals)))

    return [results_map[i] for i in range(len(goals))]
