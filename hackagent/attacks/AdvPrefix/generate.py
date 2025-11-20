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
Adversarial prefix generation module.

This module handles the generation of adversarial prefixes using uncensored language
models. It implements the first stage of the AdvPrefix attack pipeline, where
candidate prefixes are generated based on meta-prompts and target goals.

The generation process involves:
- Loading and configuring uncensored models
- Creating generation prompts from meta-templates
- Batched generation of prefix candidates
- Initial filtering and validation of generated content

Functions in this module integrate with the broader AdvPrefix pipeline and save
intermediate results for downstream processing.
"""

import logging
import os
from typing import Dict, List, Optional, Tuple, Union

import pandas as pd

from hackagent.client import AuthenticatedClient
from hackagent.logger import get_logger
from hackagent.models import AgentTypeEnum
from hackagent.router.router import AgentRouter

from .utils import create_progress_bar

logger = get_logger(__name__)

# Constants moved from main file
CUSTOM_CHAT_TEMPLATES = {
    "georgesung/llama2_7b_chat_uncensored": "<s>### HUMAN:\\n{content}\\n\\n### RESPONSE:\\n",
    "Tap-M/Luna-AI-Llama2-Uncensored": "<s>USER: {content}\\n\\nASSISTANT:",
}


def _construct_prompts(
    goals: List[str],
    meta_prefixes: List[str],
    meta_prefixes_n_samples: Union[int, List[int]],  # Allow int or list
) -> Tuple[List[Dict[str, str]], List[str], List[str]]:
    """
    Construct formatted prompts for adversarial prefix generation.

    This function creates prompts by combining target goals with meta-prefixes
    and applying appropriate chat templates. It handles both integer and list
    specifications for sample counts per meta-prefix.

    Args:
        goals: List of target goals for which to generate adversarial prefixes.
        meta_prefixes: List of meta-prefix templates to use for prompt construction.
        meta_prefixes_n_samples: Number of samples to generate per meta-prefix.
            Can be a single integer (applied to all meta-prefixes) or a list
            of integers (one per meta-prefix).

    Returns:
        A tuple containing:
        - formatted_inputs: List of formatted prompt strings ready for LLM input
        - current_goals: List of goals corresponding to each formatted input
        - expanded_meta_prefixes: List of meta-prefixes corresponding to each input

    Raises:
        ValueError: If the lengths of meta_prefixes and meta_prefixes_n_samples
            lists don't match.
        TypeError: If meta_prefixes_n_samples is neither int nor list.

    Note:
        The function applies custom chat templates for specific models when available,
        falling back to a basic USER/ASSISTANT format for unknown models.
    """
    # Handle the case where meta_prefixes_n_samples is an integer vs a list
    if isinstance(meta_prefixes_n_samples, list):
        if len(meta_prefixes) != len(meta_prefixes_n_samples):
            raise ValueError(
                "Lengths of meta_prefixes and meta_prefixes_n_samples lists must match."
            )
        n_samples_list = meta_prefixes_n_samples
    elif isinstance(meta_prefixes_n_samples, int):
        # Apply the same integer sample count to all meta prefixes
        n_samples_list = [meta_prefixes_n_samples] * len(meta_prefixes)
    else:
        raise TypeError("meta_prefixes_n_samples must be an int or a list of ints.")

    formatted_inputs = []
    current_goals = []
    expanded_meta_prefixes = []

    for goal in goals:
        for meta_prefix, n_samples in zip(meta_prefixes, n_samples_list):
            if n_samples <= 0:
                continue

            try:
                if meta_prefix in CUSTOM_CHAT_TEMPLATES:
                    prompt_content_for_template = CUSTOM_CHAT_TEMPLATES[
                        meta_prefix
                    ].format(content=goal)
                else:
                    logger.warning(
                        f"Using basic formatting for prompt construction with meta_prefix: {meta_prefix}. No matching template found."
                    )
                    # This forms the base of the "user" message if no template matches
                    prompt_content_for_template = f"USER: {goal}\\nASSISTANT:"

                # The actual text part that the LLM should complete, starting with the meta_prefix
                # This seems to be what's intended to be sent for completion.
                llm_input_text = prompt_content_for_template + meta_prefix

                # formatted_inputs will store the text that the LLM should process/complete
                formatted_inputs.extend(
                    [llm_input_text] * n_samples
                )  # This is the full text LLM sees
                current_goals.extend([goal] * n_samples)
                expanded_meta_prefixes.extend([meta_prefix] * n_samples)
            except Exception as e:
                logging.error(
                    f"Error formatting prompt for goal '{goal}' with meta_prefix '{meta_prefix}': {e}"
                )

    return formatted_inputs, current_goals, expanded_meta_prefixes


def _generate_prefixes(
    unique_goals: List[str],
    config: Dict,
    logger: logging.Logger,
    client: AuthenticatedClient,
) -> List[Dict]:
    """
    Generate adversarial prefixes using configured language models.

    This function handles the core prefix generation process by sending
    constructed prompts to either local or remote language models and
    collecting the generated responses. It supports both greedy decoding
    and random sampling strategies.

    Args:
        unique_goals: List of unique target goals for prefix generation.
        config: Configuration dictionary containing generator settings,
            including model identifier, endpoint, API keys, and generation
            parameters like temperature and max_tokens.
        logger: Logger instance for tracking generation progress and errors.
        client: Authenticated client for API communications.

    Returns:
        A list of dictionaries, each containing generation results with
        keys like 'goal', 'meta_prefix', 'generated_text', 'temperature',
        and other metadata from the generation process.

    Note:
        This function supports both local proxy endpoints and direct API
        calls. It performs generation with both greedy decoding (low temperature)
        and random sampling (higher temperature) to increase diversity
        of generated prefixes.
    """
    results = []
    generator_config = config.get("generator", {})
    if not generator_config:
        logger.error("Missing 'generator' config. Cannot generate prefixes.")
        return results

    model_name = generator_config.get("identifier")
    if not model_name:
        logger.error("Missing 'identifier' in 'generator' config.")
        return results

    generator_endpoint = generator_config.get("endpoint")
    api_key_config_value = generator_config.get(
        "api_key"
    )  # Can be env var name or direct key

    actual_api_key: str = client.token
    if api_key_config_value:
        env_key_value = os.environ.get(api_key_config_value)
        if env_key_value:
            actual_api_key = env_key_value
            logger.info(
                f"Loaded API key for generator from environment variable: {api_key_config_value}"
            )
        else:
            actual_api_key = api_key_config_value  # Assume it's the key itself
            logger.info(
                f"Using provided value directly as API key for generator (not found as env var: {api_key_config_value[:5]}...)."
            )

    logger.debug(
        f"Generator: model='{model_name}', endpoint='{generator_endpoint}', api_key_present={bool(actual_api_key)}"
    )

    try:
        prompts_to_send, current_goals, current_meta_prefixes = _construct_prompts(
            unique_goals,
            config.get("meta_prefixes", []),
            config.get("meta_prefix_samples", []),
        )
        logger.debug(f"Constructed {len(prompts_to_send)} prompts to send.")
    except Exception as e:
        logger.error(f"Error constructing prompts: {e}", exc_info=True)
        return results

    if not prompts_to_send:
        logger.warning("No prompts constructed, skipping generation.")
        return results

    # Always use AgentRouter for consistency and proper routing
    logger.info("Using AgentRouter for generator.")
    router: Optional[AgentRouter] = None
    registration_key: Optional[str] = None
    adapter_operational_config = {
        "name": model_name,
        "endpoint": generator_endpoint,
        "api_key": actual_api_key,
        "max_new_tokens": generator_config.get(
            "max_new_tokens", config.get("max_new_tokens", 100)
        ),
        "temperature": generator_config.get(
            "temperature", config.get("temperature", 0.8)
        ),
        "top_p": generator_config.get("top_p", config.get("top_p", 1.0)),
    }
    try:
        logger.info(f"Initializing AgentRouter for LiteLLM model: {model_name}")
        router = AgentRouter(
            client=client,
            name=model_name,
            agent_type=AgentTypeEnum.LITELLM,
            endpoint=generator_endpoint,
            adapter_operational_config=adapter_operational_config,
            metadata=adapter_operational_config.copy(),
            overwrite_metadata=True,
        )
        if router._agent_registry:  # type: ignore
            registration_key = next(iter(router._agent_registry.keys()))  # type: ignore
            logger.info(
                f"AgentRouter initialized. Registration key: {registration_key}"
            )
        else:
            logger.error("AgentRouter init but no agent adapter registered.")
            return results
    except Exception as e:
        logger.error(
            f"Error initializing AgentRouter for {model_name}: {e}", exc_info=True
        )
        return results

    for do_sample in [False, True]:
        progress_bar_description = (
            "[cyan]AgentRouter: Prefixes (Random Sampling)..."
            if do_sample
            else "[cyan]AgentRouter: Prefixes (Greedy Decoding)..."
        )
        logger.info(
            f"AgentRouter: {'random sampling' if do_sample else 'greedy decoding'}"
        )

        with create_progress_bar(
            progress_bar_description, total=len(prompts_to_send)
        ) as (progress_bar, task):
            for idx, current_llm_input_text in enumerate(prompts_to_send):
                goal_for_prompt = current_goals[idx]
                meta_prefix_for_prompt = current_meta_prefixes[idx]
                temperature = config.get("temperature", 0.8) if do_sample else 1e-2

                request_params = {
                    "prompt": current_llm_input_text,
                    "max_new_tokens": generator_config.get(
                        "max_new_tokens", config.get("max_new_tokens", 100)
                    ),
                    "temperature": temperature,
                    "top_p": generator_config.get("top_p", config.get("top_p", 1.0)),
                }
                # Router now returns standardized error responses instead of raising
                response = router.route_request(
                    registration_key=registration_key,
                    request_data=request_params,
                )

                error_msg = response.get("error_message")
                if error_msg:
                    # Error case - use error category in marker
                    error_cat = response.get("error_category", "Unknown")
                    generated_part = f" [ROUTER_ERROR: {error_cat}]"
                    logger.warning(
                        f"Router error for goal '{goal_for_prompt[:30]}...': {error_msg}"
                    )
                elif response.get("processed_response"):
                    completion_text = response["processed_response"]
                    # Strip the prompt if it was echoed back
                    if completion_text.startswith(current_llm_input_text):
                        generated_part = completion_text[len(current_llm_input_text) :]
                    else:
                        logger.warning(
                            "Router completion did not start with prompt. Using full response."
                        )
                        generated_part = completion_text
                else:
                    generated_part = " [ROUTER_NO_CONTENT]"

                final_prefix = meta_prefix_for_prompt + generated_part
                results.append(
                    {
                        "goal": goal_for_prompt,
                        "prefix": final_prefix,
                        "meta_prefix": meta_prefix_for_prompt,
                        "temperature": temperature,
                        "model_name": model_name,
                    }
                )
                progress_bar.update(task, advance=1)
    return results


def execute(
    goals: List[str],
    config: Dict,
    logger: logging.Logger,
    run_dir: str,
    client: AuthenticatedClient,
) -> pd.DataFrame:
    """
    Execute Step 1 of the AdvPrefix pipeline: Generate initial adversarial prefixes.

    This function orchestrates the generation of adversarial prefixes using
    uncensored language models. It processes the provided goals and configuration
    to create candidate prefixes that will be further refined in subsequent
    pipeline steps.

    Args:
        goals: List of target goals for which to generate adversarial prefixes.
            These represent the harmful behaviors or outputs the attack aims to elicit.
        config: Configuration dictionary containing generator settings including:
            - generator: Model configuration with identifier, endpoint, API keys
            - meta_prefixes: Templates for prefix generation
            - meta_prefix_samples: Number of samples per meta-prefix
            - temperature: Sampling temperature for generation
            - max_new_tokens: Maximum tokens to generate per prefix
        logger: Logger instance for tracking generation progress and debugging.
        run_dir: Directory path for saving intermediate results and logs.
            Used by the broader pipeline for file organization.
        client: Authenticated client for API communications with language models
            and the HackAgent backend.

    Returns:
        A pandas DataFrame containing the generated prefixes with columns:
        - goal: Target goal for each prefix
        - prefix: Generated adversarial prefix text
        - meta_prefix: Meta-prefix template used for generation
        - temperature: Sampling temperature used for this generation
        - model_name: Name of the model used for generation

    Note:
        This function represents Step 1 in the AdvPrefix attack pipeline.
        Generated prefixes will be processed by subsequent steps including
        cross-entropy computation, completion generation, and evaluation.

        The function handles both local proxy endpoints and remote API calls
        for language model access, and performs generation with multiple
        temperature settings to increase prefix diversity.
    """
    logger.info("Starting Step 1: Generate Prefixes")
    unique_goals = list(dict.fromkeys(goals)) if goals else []
    all_results = _generate_prefixes(
        unique_goals=unique_goals,
        config=config,
        logger=logger,
        client=client,
    )
    if not all_results:
        logger.warning("Step 1: No prefixes were generated.")
        results_df = pd.DataFrame(
            columns=["goal", "prefix", "meta_prefix", "temperature", "model_name"]
        )
    else:
        results_df = pd.DataFrame(all_results)
    logger.info(
        f"Step 1 complete. Generated {len(results_df)} total prefixes. CSV will be saved by the main pipeline."
    )
    return results_df
