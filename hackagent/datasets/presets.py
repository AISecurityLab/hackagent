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
Pre-configured dataset presets for common AI safety evaluations.

These presets provide ready-to-use configurations for popular safety benchmark
datasets from the Inspect Evals ecosystem and other sources.
"""

from typing import Any, Dict

# Registry of dataset presets
# Each preset maps to a configuration dict for HuggingFaceDatasetProvider
PRESETS: Dict[str, Dict[str, Any]] = {
    # =========================================================================
    # AgentHarm - Harmful agent task evaluation
    # Source: https://huggingface.co/datasets/ai-safety-institute/AgentHarm
    # Available configs: 'harmful', 'harmless_benign', 'chat'
    # =========================================================================
    "agentharm": {
        "provider": "huggingface",
        "path": "ai-safety-institute/AgentHarm",
        "name": "harmful",
        "goal_field": "prompt",
        "split": "test_public",
        "fallback_fields": ["input", "text"],
        "description": "AgentHarm benchmark - 176+ harmful agentic tasks (public split)",
    },
    "agentharm_benign": {
        "provider": "huggingface",
        "path": "ai-safety-institute/AgentHarm",
        "name": "harmless_benign",
        "goal_field": "prompt",
        "split": "test_public_benign",
        "fallback_fields": ["input", "text"],
        "description": "AgentHarm benchmark - benign tasks for comparison",
    },
    # =========================================================================
    # StrongREJECT - Jailbreak evaluation
    # Source: https://huggingface.co/datasets/ScaleAI-Jailbreak/strongreject
    # =========================================================================
    "strongreject": {
        "provider": "huggingface",
        "path": "Lemhf14/strongreject_small_dataset",
        "goal_field": "forbidden_prompt",
        "split": "train",
        "fallback_fields": ["prompt", "input", "text"],
        "description": "StrongREJECT - 324 forbidden prompts for jailbreak evaluation",
    },
    # =========================================================================
    # XSTest - Safety exaggeration evaluation
    # Source: https://huggingface.co/datasets/Paul/xstest
    # =========================================================================
    "xstest": {
        "provider": "huggingface",
        "path": "Paul/xstest",
        "goal_field": "prompt",
        "split": "test",
        "fallback_fields": ["input", "text"],
        "description": "XSTest - prompts to test for safety exaggeration/over-refusal",
    },
    # =========================================================================
    # HarmBench - Standard behaviors
    # Source: https://huggingface.co/datasets/harmbench/harmbench_behaviors_text_all
    # =========================================================================
    "harmbench": {
        "provider": "huggingface",
        "path": "harmbench/harmbench_behaviors_text_all",
        "goal_field": "goal",
        "split": "train",
        "fallback_fields": ["behavior", "prompt", "input"],
        "description": "HarmBench - harmful behavior prompts",
    },
    "harmbench_standard": {
        "provider": "huggingface",
        "path": "harmbench/harmbench_behaviors_text_all",
        "name": "standard",
        "goal_field": "goal",
        "split": "train",
        "fallback_fields": ["behavior", "prompt", "input"],
        "description": "HarmBench - standard harmful behaviors",
    },
    # =========================================================================
    # AdvBench - Adversarial behaviors
    # Source: https://huggingface.co/datasets/walledai/AdvBench
    # =========================================================================
    "advbench": {
        "provider": "huggingface",
        "path": "walledai/AdvBench",
        "goal_field": "goal",
        "split": "train",
        "fallback_fields": ["prompt", "input", "text"],
        "description": "AdvBench - 520 adversarial harmful goals",
    },
    # =========================================================================
    # TruthfulQA - Truthfulness evaluation
    # Source: https://huggingface.co/datasets/truthfulqa/truthful_qa
    # =========================================================================
    "truthfulqa": {
        "provider": "huggingface",
        "path": "truthfulqa/truthful_qa",
        "name": "generation",
        "goal_field": "question",
        "split": "validation",
        "fallback_fields": ["input", "text"],
        "description": "TruthfulQA - questions to evaluate truthfulness",
    },
    # =========================================================================
    # SimpleSafetyTests - Basic safety tests
    # Source: https://huggingface.co/datasets/Bertievidgen/SimpleSafetyTests
    # =========================================================================
    "simplesafetytests": {
        "provider": "huggingface",
        "path": "Bertievidgen/SimpleSafetyTests",
        "goal_field": "prompt",
        "split": "test",
        "fallback_fields": ["input", "text"],
        "description": "SimpleSafetyTests - 100 clear-cut harmful prompts",
    },
    # =========================================================================
    # WMDP - Weapons of Mass Destruction Proxy
    # Source: https://huggingface.co/datasets/cais/wmdp
    # Note: This is a multiple-choice dataset, goal_field extracts questions
    # =========================================================================
    "wmdp_bio": {
        "provider": "huggingface",
        "path": "cais/wmdp",
        "name": "wmdp-bio",
        "goal_field": "question",
        "split": "test",
        "fallback_fields": ["input", "text"],
        "description": "WMDP Bio - biosecurity hazardous knowledge questions",
    },
    "wmdp_cyber": {
        "provider": "huggingface",
        "path": "cais/wmdp",
        "name": "wmdp-cyber",
        "goal_field": "question",
        "split": "test",
        "fallback_fields": ["input", "text"],
        "description": "WMDP Cyber - cybersecurity hazardous knowledge questions",
    },
    "wmdp_chem": {
        "provider": "huggingface",
        "path": "cais/wmdp",
        "name": "wmdp-chem",
        "goal_field": "question",
        "split": "test",
        "fallback_fields": ["input", "text"],
        "description": "WMDP Chem - chemistry hazardous knowledge questions",
    },
    # =========================================================================
    # DO-NOT-ANSWER - Responsible AI evaluation
    # Source: https://huggingface.co/datasets/LibrAI/do-not-answer
    # =========================================================================
    "donotanswer": {
        "provider": "huggingface",
        "path": "LibrAI/do-not-answer",
        "goal_field": "question",
        "split": "train",
        "fallback_fields": ["prompt", "input", "text"],
        "description": "Do-Not-Answer - 939 questions LLMs should refuse to answer",
    },
    # =========================================================================
    # CoCoNot - Context-conditioned safety
    # Source: https://huggingface.co/datasets/allenai/coconot
    # =========================================================================
    "coconot": {
        "provider": "huggingface",
        "path": "allenai/coconot",
        "goal_field": "prompt",
        "split": "test",
        "fallback_fields": ["request", "input", "text"],
        "description": "CoCoNot - context-conditioned refusal evaluation",
    },
}


def get_preset(name: str) -> Dict[str, Any]:
    """
    Get a preset configuration by name.

    Args:
        name: The preset name (case-insensitive).

    Returns:
        The preset configuration dictionary.

    Raises:
        ValueError: If the preset is not found.
    """
    name_lower = name.lower().replace("-", "_").replace(" ", "_")

    if name_lower not in PRESETS:
        available = ", ".join(sorted(PRESETS.keys()))
        raise ValueError(f"Unknown preset: '{name}'. Available presets: {available}")

    return PRESETS[name_lower].copy()


def list_presets() -> Dict[str, str]:
    """
    List all available presets with their descriptions.

    Returns:
        Dictionary mapping preset names to descriptions.
    """
    return {
        name: config.get("description", "No description")
        for name, config in PRESETS.items()
    }
