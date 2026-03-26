# Copyright 2025 - AI4I. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
FlipAttack generation and execution module.

Generates flipped prompts by calling :meth:`FlipAttack.generate` on the
attack instance passed via ``config["_self"]``, then executes them against
the target model via HackAgent's AgentRouter.

Result Tracking:
    Uses Tracker (passed via config["_tracker"]) to add interaction traces
    per goal during generation and execution.
"""

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hackagent.router.router import AgentRouter

if TYPE_CHECKING:
    from hackagent.router.tracking import Tracker


def execute(
    goals: List[str],
    agent_router: AgentRouter,
    config: Dict[str, Any],
    logger: logging.Logger,
) -> List[Dict]:
    """
    Generate flipped prompts and execute them against target model.

    Args:
        goals: List of harmful prompts to flip
        agent_router: Router for target model communication
        config: Configuration dictionary with flipattack_params
        logger: Logger instance

    Returns:
        List of dicts with goal, flipped prompt, and response
    """
    # Retrieve the FlipAttack instance (carries all obfuscation methods).
    fa = config.get("_self")
    if fa is None:
        raise RuntimeError("config['_self'] must be set to the FlipAttack instance.")

    # Extract parameters (still needed for logging and result fields).
    fa_params = config.get("flipattack_params", {})
    flip_mode = fa_params.get("flip_mode", "FCS")
    cot = fa_params.get("cot", False)
    lang_gpt = fa_params.get("lang_gpt", False)
    few_shot = fa_params.get("few_shot", False)

    # Extract tracker for per-goal result tracking
    tracker: Optional["Tracker"] = config.get("_tracker")

    logger.info(f"Initializing FlipAttack with mode={flip_mode}")
    logger.info(f"Enhancements: CoT={cot}, LangGPT={lang_gpt}, FewShot={few_shot}")

    if tracker:
        logger.info("📊 Generation tracking via Tracker enabled")

    victim_key = str(agent_router.backend_agent.id)
    # All goals are independent — fire them in parallel so the victim GPU
    # receives batch_size requests concurrently instead of one at a time.
    batch_size = max(1, config.get("batch_size", 16))
    raw_goal_index_offset = config.get("_goal_index_offset", 0)
    try:
        goal_index_offset = int(raw_goal_index_offset)
    except (TypeError, ValueError):
        goal_index_offset = 0
    _lock = threading.Lock()
    results_map: Dict[int, Dict[str, Any]] = {}

    def _process_goal(idx_goal: tuple) -> None:
        idx, goal_text = idx_goal
        _t0 = time.perf_counter()
        logger.info(f"Processing goal {idx + 1}/{len(goals)}")

        # Step 1: Generate flipped prompt (pure Python — no HTTP, always fast)
        try:
            log, attack_messages = fa.generate(goal_text)
        except Exception as e:
            logger.error(f"Generation failed for goal {idx + 1}: {e}")
            with _lock:
                results_map[idx] = {
                    "goal": goal_text,
                    "flip_mode": flip_mode,
                    "error": f"Generation failed: {str(e)}",
                    "response": None,
                }
            return

        # Extract system and user prompts
        system_prompt = attack_messages[0]["content"] if attack_messages else ""
        user_prompt = attack_messages[1]["content"] if len(attack_messages) > 1 else ""
        full_prompt = f"{system_prompt}\n\n{user_prompt}".strip()
        logger.info(
            f"[Goal {idx + 1}/{len(goals)}] Modified prompt generated:\n{full_prompt}"
        )

        # Step 2: Execute against target model (HTTP — parallelised here)
        request_data = {"prompt": full_prompt}
        max_tokens = config.get("max_tokens")
        if max_tokens is not None:
            request_data["max_tokens"] = max_tokens
        _request_t0 = time.perf_counter()
        logger.info(
            f"[Goal {idx + 1}/{len(goals)}] Sending modified prompt to target model"
        )
        try:
            response = agent_router.route_request(
                registration_key=victim_key,
                request_data=request_data,
            )
        except Exception as e:
            logger.error(f"Execution failed for goal {idx + 1}: {e}")
            with _lock:
                results_map[idx] = {
                    "goal": goal_text,
                    "flip_mode": flip_mode,
                    "flip_log": log,
                    "system_prompt": system_prompt,
                    "user_prompt": user_prompt,
                    "full_prompt": full_prompt,
                    "error": f"Execution failed: {str(e)}",
                    "response": None,
                }
            return

        _request_elapsed = round(time.perf_counter() - _request_t0, 3)
        logger.info(
            f"[Goal {idx + 1}/{len(goals)}] Target model responded in {_request_elapsed}s"
        )

        generated_text = response.get("generated_text")
        error_message = response.get("error_message")

        if generated_text:
            logger.info(
                f"[Goal {idx + 1}/{len(goals)}] Target response:\n{generated_text}"
            )
        else:
            logger.info(f"[Goal {idx + 1}/{len(goals)}] Target response is empty")

        if error_message:
            logger.warning(
                f"[Goal {idx + 1}/{len(goals)}] Target error: {error_message}"
            )

        with _lock:
            _goal_elapsed = round(time.perf_counter() - _t0, 3)
            # Add trace to goal's Result via Tracker
            if tracker:
                goal_ctx = tracker.get_goal_context(goal_index_offset + idx)
                if goal_ctx:
                    tracker.add_interaction_trace(
                        ctx=goal_ctx,
                        request=request_data,
                        response={
                            "generated_text": generated_text,
                            "error_message": error_message,
                        },
                        step_name=f"FlipAttack Generation ({flip_mode})",
                        metadata={
                            "flip_mode": flip_mode,
                            "flip_log": log,
                            "system_prompt": system_prompt,
                            "user_prompt": user_prompt,
                            "elapsed_s": _goal_elapsed,
                        },
                    )
            results_map[idx] = {
                "goal": goal_text,
                "flip_mode": flip_mode,
                "flip_log": log,
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "full_prompt": full_prompt,
                "response": generated_text,
                "error": error_message,
                "generation_elapsed_s": _goal_elapsed,
            }

        if error_message:
            logger.warning(f"Goal {idx + 1} failed: {error_message}")

    with ThreadPoolExecutor(max_workers=batch_size) as pool:
        list(pool.map(_process_goal, enumerate(goals)))

    results = [results_map[i] for i in range(len(goals))]
    logger.info(f"Generated and executed {len(results)} attacks")
    return results
