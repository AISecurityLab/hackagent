# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
MML attack generation and execution module.

Encodes harmful prompts into images using the configured MML encoding mode,
constructs multimodal messages (text + image), and sends them to the target
Vision-Language Model via HackAgent's AgentRouter.

Result Tracking:
    Uses Tracker (passed via config["_tracker"]) to add interaction traces
    per goal during generation and execution.
"""

import logging
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hackagent.router.router import AgentRouter

from .image_encoder import encode_prompt
from .prompts import get_prompt_template

if TYPE_CHECKING:
    from hackagent.router.tracking import Tracker


def _random_shuffle_words(sentence: str) -> List[str]:
    """Split sentence into words and shuffle them randomly."""
    words = sentence.split()
    random.shuffle(words)
    return words


def _build_text_prompt(
    encoding_mode: str,
    prompt_style: str,
    encoding_result: Dict[str, Any],
) -> str:
    """Build the text prompt to accompany the encoded image.

    Args:
        encoding_mode: The encoding mode used.
        prompt_style: Prompt framing style ("game" or "control").
        encoding_result: Result dict from the image encoder.

    Returns:
        The formatted text prompt string.
    """
    template = get_prompt_template(encoding_mode, prompt_style)

    format_kwargs = {}
    if "scrambled_words" in encoding_result:
        format_kwargs["scrambled_words"] = str(encoding_result["scrambled_words"])
    if "replacement_dict" in encoding_result:
        format_kwargs["replacement_dict"] = str(encoding_result["replacement_dict"])

    return template.format(**format_kwargs)


def _build_multimodal_messages(
    text_prompt: str, image_data_url: str
) -> List[Dict[str, Any]]:
    """Build OpenAI-compatible multimodal message list.

    Args:
        text_prompt: The textual instruction prompt.
        image_data_url: Base64-encoded image data URL.

    Returns:
        List of message dicts with multimodal content.
    """
    return [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": text_prompt},
                {
                    "type": "image_url",
                    "image_url": {"url": image_data_url},
                },
            ],
        }
    ]


def execute(
    goals: List[str],
    agent_router: AgentRouter,
    config: Dict[str, Any],
    logger: logging.Logger,
) -> List[Dict]:
    """
    Generate MML-encoded images and execute attacks against target model.

    Args:
        goals: List of harmful prompts to encode into images.
        agent_router: Router for target model communication.
        config: Configuration dictionary with mml_params.
        logger: Logger instance.

    Returns:
        List of dicts with goal, encoding info, prompt, and response.
    """
    mml_params = config.get("mml_params", {})
    encoding_mode = mml_params.get("encoding_mode", "word_replacement")
    prompt_style = mml_params.get("prompt_style", "game")
    image_width = mml_params.get("image_width", 800)
    image_height = mml_params.get("image_height", 400)
    font_size = mml_params.get("font_size", 24)
    background_color = mml_params.get("background_color", "white")
    text_color = mml_params.get("text_color", "black")
    num_replacements = mml_params.get("num_replacements", 3)

    # Extract tracker for per-goal result tracking
    tracker: Optional["Tracker"] = config.get("_tracker")

    logger.info(f"Initializing MML attack with encoding_mode={encoding_mode}")
    logger.info(f"Prompt style: {prompt_style}")

    if tracker:
        logger.info("📊 Generation tracking via Tracker enabled")

    victim_key = str(agent_router.backend_agent.id)
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

        # Step 1: Encode the harmful prompt into an image
        encode_kwargs: Dict[str, Any] = {
            "image_width": image_width,
            "image_height": image_height,
            "font_size": font_size,
            "background_color": background_color,
            "text_color": text_color,
        }
        if encoding_mode == "word_replacement":
            encode_kwargs["num_replacements"] = num_replacements

        try:
            encoding_result = encode_prompt(
                prompt=goal_text,
                encoding_mode=encoding_mode,
                **encode_kwargs,
            )
        except Exception as e:
            logger.error(f"Encoding failed for goal {idx + 1}: {e}")
            with _lock:
                results_map[idx] = {
                    "goal": goal_text,
                    "encoding_mode": encoding_mode,
                    "error": f"Encoding failed: {str(e)}",
                    "response": None,
                }
            return

        # Step 2: Build the text prompt
        try:
            text_prompt = _build_text_prompt(
                encoding_mode=encoding_mode,
                prompt_style=prompt_style,
                encoding_result=encoding_result,
            )
        except Exception as e:
            logger.error(f"Prompt building failed for goal {idx + 1}: {e}")
            with _lock:
                results_map[idx] = {
                    "goal": goal_text,
                    "encoding_mode": encoding_mode,
                    "error": f"Prompt building failed: {str(e)}",
                    "response": None,
                }
            return

        # Step 3: Build multimodal messages
        image_data_url = encoding_result["image_data_url"]
        messages = _build_multimodal_messages(text_prompt, image_data_url)

        logger.info(
            f"[Goal {idx + 1}/{len(goals)}] Encoded prompt with mode={encoding_mode}"
        )

        # Step 4: Execute against target model
        request_data: Dict[str, Any] = {"messages": messages}
        max_tokens = config.get("max_tokens")
        if max_tokens is not None:
            request_data["max_tokens"] = max_tokens

        _request_t0 = time.perf_counter()
        logger.info(
            f"[Goal {idx + 1}/{len(goals)}] Sending multimodal request to target model"
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
                    "encoding_mode": encoding_mode,
                    "text_prompt": text_prompt,
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
                        request={"prompt": text_prompt, "encoding_mode": encoding_mode},
                        response={
                            "generated_text": generated_text,
                            "error_message": error_message,
                        },
                        step_name=f"MML Generation ({encoding_mode})",
                        metadata={
                            "encoding_mode": encoding_mode,
                            "prompt_style": prompt_style,
                            "text_prompt": text_prompt,
                            "image_data_url": image_data_url,
                            "elapsed_s": _goal_elapsed,
                        },
                    )
            results_map[idx] = {
                "goal": goal_text,
                "encoding_mode": encoding_mode,
                "text_prompt": text_prompt,
                "full_prompt": text_prompt,
                "image_data_url": image_data_url,
                "response": generated_text,
                "error": error_message,
                "generation_elapsed_s": _goal_elapsed,
            }

        if error_message:
            logger.warning(f"Goal {idx + 1} failed: {error_message}")

    with ThreadPoolExecutor(max_workers=batch_size) as pool:
        list(pool.map(_process_goal, enumerate(goals)))

    results = [results_map[i] for i in range(len(goals))]
    logger.info(f"Generated and executed {len(results)} MML attacks")
    return results
