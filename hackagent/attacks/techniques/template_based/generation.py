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
Template generation module for template-based attacks.

Generates attack prompts by combining predefined templates with goals.
"""

import logging
from typing import Any, Dict, List

import pandas as pd

from hackagent.attacks.shared.templates import AttackTemplates
from hackagent.router.router import AgentRouter


logger = logging.getLogger("hackagent.attacks.template_based.generation")


def generate_prompts(
    goals: List[str],
    config: Dict[str, Any],
    logger: logging.Logger,
) -> pd.DataFrame:
    """
    Generate attack prompts using templates.

    Args:
        goals: List of harmful goals to generate attacks for
        config: Configuration dictionary
        logger: Logger instance

    Returns:
        DataFrame with columns: goal, template_category, template, attack_prompt
    """
    logger.info(f"Generating template-based prompts for {len(goals)} goals...")

    # Get template configuration
    categories = config.get("template_categories", [])
    templates_per_cat = config.get("templates_per_category", 3)

    results = []

    for goal in goals:
        for category in categories:
            # Get templates for this category
            templates = AttackTemplates.get_templates_by_category(
                category, limit=templates_per_cat
            )

            for template in templates:
                # Format template with goal
                attack_prompt = template.format(harmful_request=goal)

                results.append(
                    {
                        "goal": goal,
                        "template_category": category,
                        "template": template,
                        "attack_prompt": attack_prompt,
                    }
                )

    df = pd.DataFrame(results)
    logger.info(
        f"Generated {len(df)} attack prompts across {len(categories)} categories"
    )

    return df


def execute_prompts(
    df: pd.DataFrame,
    agent_router: AgentRouter,
    config: Dict[str, Any],
    logger: logging.Logger,
) -> pd.DataFrame:
    """
    Execute attack prompts against target model.

    Args:
        df: DataFrame with attack_prompt column
        agent_router: Target agent router
        config: Configuration dictionary
        logger: Logger instance

    Returns:
        DataFrame with added completion column
    """
    logger.info(f"Executing {len(df)} prompts against target model...")

    max_tokens = config.get("max_new_tokens", 150)
    temperature = config.get("temperature", 0.7)
    n_samples = config.get("n_samples_per_template", 1)

    completions = []

    for idx, row in df.iterrows():
        try:
            # Prepare request
            request_data = {
                "messages": [{"role": "user", "content": row["attack_prompt"]}],
                "max_tokens": max_tokens,
                "temperature": temperature,
            }

            # Get completion(s)
            for _ in range(n_samples):
                response = agent_router.route_request(
                    registration_key=list(agent_router._agent_registry.keys())[0],
                    request_data=request_data,
                )

                completion = ""
                if response and hasattr(response, "choices") and response.choices:
                    completion = response.choices[0].message.content or ""

                completions.append(
                    {
                        **row.to_dict(),
                        "completion": completion,
                        "response_length": len(completion),
                    }
                )

        except Exception as e:
            logger.warning(f"Error executing prompt {idx}: {e}")
            completions.append(
                {
                    **row.to_dict(),
                    "completion": "",
                    "response_length": 0,
                    "error": str(e),
                }
            )

    result_df = pd.DataFrame(completions)
    logger.info(f"Execution complete. Got {len(result_df)} completions")

    return result_df


def execute(
    goals: List[str],
    agent_router: AgentRouter,
    config: Dict[str, Any],
    logger: logging.Logger,
) -> pd.DataFrame:
    """
    Complete generation pipeline: generate prompts and execute them.

    Args:
        goals: List of harmful goals
        agent_router: Target agent router
        config: Configuration dictionary
        logger: Logger instance

    Returns:
        DataFrame with goals, prompts, and completions
    """
    # Step 1: Generate prompts
    prompts_df = generate_prompts(goals, config, logger)

    # Step 2: Execute prompts
    results_df = execute_prompts(prompts_df, agent_router, config, logger)

    return results_df
