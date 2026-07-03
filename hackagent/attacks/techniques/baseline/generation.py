# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Generation module for the Baseline attack.

Sends each goal directly to the target model without any transformation.
"""

import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional

from hackagent.attacks.shared.response_utils import (
    extract_response_content,
    is_guardrail_response,
)
from hackagent.router.router import AgentRouter
from hackagent.router.tracking import Tracker


logger = logging.getLogger("hackagent.attacks.baseline.generation")


def _safe_goal_index(value: Any, fallback: int = -1) -> int:
    """Best-effort conversion of goal index to int."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _safe_positive_int(value: Any, fallback: int) -> int:
    """Best-effort conversion to positive int with fallback."""
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return fallback
    return parsed if parsed > 0 else fallback


def execute(
    goals: List[str],
    agent_router: AgentRouter,
    config: Dict[str, Any],
    logger: logging.Logger,
    goal_tracker: Optional[Tracker] = None,
) -> List[Dict[str, Any]]:
    """
    Send each goal directly to the target model and collect responses.

    Args:
        goals: List of goal strings to send as-is.
        agent_router: Target agent router.
        config: Configuration dictionary.
        logger: Logger instance.
        goal_tracker: Optional Tracker for per-goal result tracking.

    Returns:
        List of dicts with keys: goal, goal_index, attack_prompt, completion,
        response_length, and optionally guardrail_blocked or error.
    """
    logger.info(f"Executing baseline (direct) prompts for {len(goals)} goals...")

    max_tokens = config.get("max_tokens", 1024)
    temperature = config.get("temperature", 0.0)
    goal_index_offset = _safe_goal_index(config.get("_goal_index_offset", 0), 0)
    batch_size = _safe_positive_int(config.get("batch_size", 16), 16)

    # Tracking setup
    run_id = config.get("_run_id")
    client = config.get("_backend") or config.get("_client")

    if not goal_tracker:
        goal_tracker = config.get("_tracker")

    if goal_tracker:
        logger.info("📊 Using Tracker for per-goal result tracking")
    elif run_id and client:
        logger.info(f"📊 Creating Tracker for baseline (run_id={run_id})")
        goal_tracker = Tracker(
            backend=client,
            run_id=run_id,
            logger=logger,
            attack_type="Baseline",
            category_classifier_config=config.get("category_classifier"),
            event_bus=config.get("_tui_event_bus"),
        )
    else:
        logger.warning("⚠️ Missing tracking context - results will NOT be created!")

    # Create goal contexts for tracking
    goal_contexts: Dict[int, Any] = {}
    if goal_tracker:
        for local_idx, goal in enumerate(goals):
            goal_idx = goal_index_offset + local_idx
            ctx = goal_tracker.get_goal_context(goal_idx)
            if not ctx:
                ctx = goal_tracker.create_goal_result(
                    goal=goal,
                    goal_index=goal_idx,
                    initial_metadata={"attack_type": "Baseline"},
                )
            goal_contexts[goal_idx] = ctx

    # Execute goals in parallel
    _lock = threading.Lock()
    results_map: Dict[int, Dict[str, Any]] = {}

    def _execute_goal(local_idx: int) -> None:
        goal_idx = goal_index_offset + local_idx
        goal = goals[local_idx]
        goal_ctx = goal_contexts.get(goal_idx) if goal_tracker else None

        try:
            request_data = {
                "messages": [{"role": "user", "content": goal}],
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
            response = agent_router.route_request(
                registration_key=list(agent_router._agent_registry.keys())[0],
                request_data=request_data,
            )
            completion = extract_response_content(response, logger) or ""
            adapter_error = None
            if isinstance(response, dict):
                adapter_error = response.get("error_message") or response.get("error")

            row: Dict[str, Any] = {
                "goal": goal,
                "goal_index": goal_idx,
                "attack_prompt": goal,
                "completion": completion,
                "response_length": len(completion),
            }
            if isinstance(response, dict) and is_guardrail_response(response):
                row["guardrail_blocked"] = True
            elif adapter_error and not completion:
                row["error"] = str(adapter_error)

            with _lock:
                if goal_tracker and goal_ctx:
                    goal_tracker.add_interaction_trace(
                        ctx=goal_ctx,
                        request={"prompt": goal},
                        response=response,
                        step_name="Baseline: Direct Request",
                        metadata={
                            "response_length": len(completion),
                        },
                    )
                results_map[local_idx] = row

        except Exception as e:
            logger.warning(f"Error executing goal {goal_idx}: {e}")
            with _lock:
                if goal_tracker and goal_ctx:
                    goal_tracker.add_custom_trace(
                        ctx=goal_ctx,
                        step_name="Execution Error",
                        content={
                            "error": str(e),
                            "goal": goal[:200],
                        },
                    )
                results_map[local_idx] = {
                    "goal": goal,
                    "goal_index": goal_idx,
                    "attack_prompt": goal,
                    "completion": "",
                    "response_length": 0,
                    "error": str(e),
                }

    workers = min(len(goals), batch_size)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(_execute_goal, range(len(goals))))

    results = [results_map[i] for i in range(len(goals))]
    logger.info(f"Baseline execution complete: {len(results)} goals processed")
    return results
