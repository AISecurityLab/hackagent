# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Template generation module for baseline attacks.

Generates attack prompts by combining predefined templates with goals.

Result Tracking:
    Uses Tracker to create one Result per goal, with traces for each
    template attempt. This provides better organization where each Result
    represents a complete attack attempt on a single goal.
"""

import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional

from hackagent.attacks.shared.response_utils import extract_response_content
from hackagent.attacks.generator import AttackTemplates
from hackagent.attacks.shared.progress import create_progress_bar
from hackagent.router.router import AgentRouter
from hackagent.router.tracking import Tracker


logger = logging.getLogger("hackagent.attacks.baseline.generation")


def generate_prompts(
    goals: List[str],
    config: Dict[str, Any],
    logger: logging.Logger,
) -> List[Dict[str, Any]]:
    """
    Generate attack prompts using templates.

    Args:
        goals: List of harmful goals to generate attacks for
        config: Configuration dictionary
        logger: Logger instance

    Returns:
        List of dicts with keys: goal, template_category, template, attack_prompt
    """
    logger.info(f"Generating baseline prompts for {len(goals)} goals...")

    # Get template configuration
    categories = config.get("template_categories", [])
    templates_per_cat = config.get("templates_per_category", 3)

    results = []

    for goal in goals:
        for category in categories:
            # Get templates for this category
            all_templates = AttackTemplates.get_by_category(category)
            templates = all_templates[:templates_per_cat]  # Limit number of templates

            for template in templates:
                # Format template with goal
                attack_prompt = template.format(goal=goal)

                results.append(
                    {
                        "goal": goal,
                        "template_category": category,
                        "template": template,
                        "attack_prompt": attack_prompt,
                    }
                )

    logger.info(
        f"Generated {len(results)} attack prompts across {len(categories)} categories"
    )

    return results


def execute_prompts(
    data: List[Dict[str, Any]],
    agent_router: AgentRouter,
    config: Dict[str, Any],
    logger: logging.Logger,
    goal_tracker: Optional[Tracker] = None,
) -> List[Dict[str, Any]]:
    """
    Execute attack prompts against target model.

    Uses Tracker (if provided) to add traces for each interaction,
    grouping all attempts under a single Result per goal.

    Args:
        data: List of dicts with attack_prompt key
        agent_router: Target agent router
        config: Configuration dictionary
        logger: Logger instance
        goal_tracker: Optional Tracker for per-goal result tracking

    Returns:
        List of dicts with added completion key
    """
    logger.info(f"Executing {len(data)} prompts against target model...")

    max_tokens = config.get("max_new_tokens", 150)
    temperature = config.get("temperature", 0.7)
    n_samples = config.get("n_samples_per_template", 1)

    # Extract tracking information from config (for backwards compatibility)
    run_id = config.get("_run_id")
    client = config.get("_client")

    # Use Tracker if provided, otherwise log warning
    if goal_tracker:
        logger.info("📊 Using Tracker for per-goal result tracking")
    elif run_id and client:
        logger.info(f"📊 Creating Tracker for baseline (run_id={run_id})")
        goal_tracker = Tracker(
            client=client,
            run_id=run_id,
            logger=logger,
            attack_type="baseline",
        )
    else:
        logger.warning("⚠️ Missing tracking context - results will NOT be created!")

    total_requests = len(data) * n_samples

    # Group data by goal for organized tracking
    goals_data: Dict[str, List[Dict[str, Any]]] = {}
    for row in data:
        goal = row.get("goal", "unknown")
        if goal not in goals_data:
            goals_data[goal] = []
        goals_data[goal].append(row)

    # Create goal results upfront if using Tracker
    goal_contexts = {}
    if goal_tracker:
        for goal_idx, goal in enumerate(goals_data.keys()):
            ctx = goal_tracker.create_goal_result(
                goal=goal,
                goal_index=goal_idx,
                initial_metadata={
                    "num_templates": len(goals_data[goal]),
                    "n_samples_per_template": n_samples,
                },
            )
            goal_contexts[goal] = ctx

    # Parallel execution: each row's HTTP calls are independent.
    # n_samples inner loop stays sequential per row (usually 1; ordering matters).
    batch_size = max(1, config.get("batch_size", 16))
    _lock = threading.Lock()
    # results_map[row_idx] = list of completion dicts for that row
    results_map: Dict[int, List[Dict[str, Any]]] = {}
    goals_keys = list(goals_data.keys())

    def _execute_row(idx_row: tuple) -> None:
        idx, row = idx_row
        goal = row.get("goal", "unknown")
        goal_ctx = goal_contexts.get(goal) if goal_tracker else None
        row_completions: List[Dict[str, Any]] = []
        goal_index = goals_keys.index(goal) if goal in goals_data else idx

        try:
            request_data = {
                "messages": [{"role": "user", "content": row["attack_prompt"]}],
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
            for sample_idx in range(n_samples):
                response = agent_router.route_request(
                    registration_key=list(agent_router._agent_registry.keys())[0],
                    request_data=request_data,
                )
                completion = extract_response_content(response, logger) or ""
                with _lock:
                    if goal_tracker and goal_ctx:
                        goal_tracker.add_interaction_trace(
                            ctx=goal_ctx,
                            request=request_data,
                            response=response,
                            step_name=f"Template: {row.get('template_category', 'unknown')}",
                            metadata={
                                "template_category": row.get("template_category"),
                                "sample_index": sample_idx,
                                "response_length": len(completion),
                            },
                        )
                row_completions.append(
                    {
                        **row,
                        "completion": completion,
                        "response_length": len(completion),
                        "goal_index": goal_index,
                    }
                )
        except Exception as e:
            logger.warning(f"Error executing prompt {idx}: {e}")
            with _lock:
                if goal_tracker and goal_ctx:
                    goal_tracker.add_custom_trace(
                        ctx=goal_ctx,
                        step_name="Execution Error",
                        content={
                            "error": str(e),
                            "template_category": row.get("template_category"),
                            "attack_prompt": row.get("attack_prompt", "")[:200],
                        },
                    )
            row_completions.append(
                {
                    **row,
                    "completion": "",
                    "response_length": 0,
                    "error": str(e),
                    "goal_index": goal_index,
                }
            )
        with _lock:
            results_map[idx] = row_completions

    with create_progress_bar("[cyan]Executing baseline prompts...", total_requests) as (
        progress_bar,
        task,
    ):
        with ThreadPoolExecutor(max_workers=batch_size) as pool:
            for _ in pool.map(_execute_row, enumerate(data)):
                progress_bar.update(task, advance=n_samples)

    # Reconstruct completions in original row order
    completions = []
    for i in range(len(data)):
        completions.extend(results_map.get(i, []))

    logger.info(f"Execution complete. Got {len(completions)} completions")

    # Store goal_tracker in config for evaluation phase to use
    if goal_tracker:
        config["_tracker"] = goal_tracker
        config["_goal_contexts"] = goal_contexts

    return completions


def execute(
    goals: List[str],
    agent_router: AgentRouter,
    config: Dict[str, Any],
    logger: logging.Logger,
) -> List[Dict[str, Any]]:
    """
    Complete generation pipeline: generate prompts and execute them.

    Args:
        goals: List of harmful goals
        agent_router: Target agent router
        config: Configuration dictionary
        logger: Logger instance

    Returns:
        List of dicts with goals, prompts, and completions
    """
    # Step 1: Generate prompts
    prompts_data = generate_prompts(goals, config, logger)

    # Step 2: Execute prompts
    results_data = execute_prompts(prompts_data, agent_router, config, logger)

    return results_data
