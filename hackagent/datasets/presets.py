# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

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
    # Source: https://huggingface.co/datasets/walledai/HarmBench
    # Available configs: 'standard', 'contextual', 'copyright'
    # =========================================================================
    "harmbench": {
        "provider": "huggingface",
        "path": "walledai/HarmBench",
        "name": "standard",
        "goal_field": "prompt",
        "split": "train",
        "fallback_fields": ["behavior", "goal", "input"],
        "description": "HarmBench - 200 standard harmful behavior prompts",
    },
    "harmbench_contextual": {
        "provider": "huggingface",
        "path": "walledai/HarmBench",
        "name": "contextual",
        "goal_field": "prompt",
        "split": "train",
        "fallback_fields": ["behavior", "goal", "input"],
        "description": "HarmBench - 100 contextual harmful behavior prompts",
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
    # =========================================================================
    # JailbreakBench - Curated jailbreak behaviors (NeurIPS 2024)
    # Source: https://huggingface.co/datasets/JailbreakBench/JBB-Behaviors
    # Available configs: 'behaviors' (harmful + benign splits)
    # Paper: https://arxiv.org/abs/2404.01318
    # =========================================================================
    "jailbreakbench": {
        "provider": "huggingface",
        "path": "JailbreakBench/JBB-Behaviors",
        "name": "behaviors",
        "goal_field": "Goal",
        "split": "harmful",
        "fallback_fields": ["goal", "prompt", "input", "text"],
        "description": (
            "JailbreakBench - 100 curated misuse behaviors across 10 OpenAI "
            "policy categories (NeurIPS 2024 Datasets & Benchmarks)"
        ),
    },
    # =========================================================================
    # BeaverTails - Multi-category safety QA dataset
    # Source: https://huggingface.co/datasets/PKU-Alignment/BeaverTails
    # 14 harm categories: animal abuse, child abuse, discrimination, drugs,
    # financial crime, hate speech, misinformation, privacy, self-harm,
    # sexual content, terrorism, violence, and more
    # Paper: https://arxiv.org/abs/2307.04657
    # =========================================================================
    "beavertails": {
        "provider": "huggingface",
        "path": "PKU-Alignment/BeaverTails",
        "goal_field": "prompt",
        "split": "330k_test",
        "fallback_fields": ["question", "input", "text"],
        "description": (
            "BeaverTails - 330K+ safety-labeled QA pairs across 14 harm "
            "categories including discrimination, privacy, violence, and more"
        ),
    },
    # =========================================================================
    # HarmfulQA - Red-teaming harmful questions across 10 topics
    # Source: https://huggingface.co/datasets/declare-lab/HarmfulQA
    # Topics: science, history, math, literature, philosophy, social sciences,
    # health, geography, education, business
    # Paper: https://arxiv.org/abs/2308.09662
    # =========================================================================
    "harmfulqa": {
        "provider": "huggingface",
        "path": "declare-lab/HarmfulQA",
        "goal_field": "question",
        "split": "train",
        "fallback_fields": ["prompt", "input", "text"],
        "description": (
            "HarmfulQA - 1,960 harmful questions across 10 topics with "
            "red/blue conversations for safety benchmarking"
        ),
    },
    # =========================================================================
    # SALAD-Bench - Hierarchical safety benchmark
    # Source: https://huggingface.co/datasets/OpenSafetyLab/Salad-Data
    # Available configs: 'base_set', 'attack_enhanced_set',
    #                    'defense_enhanced_set', 'mcq_set'
    # Taxonomy: 3-level harm categories (representation, misinformation,
    # malicious use, human autonomy, etc.)
    # Paper: https://arxiv.org/abs/2402.05044
    # =========================================================================
    "saladbench": {
        "provider": "huggingface",
        "path": "OpenSafetyLab/Salad-Data",
        "name": "base_set",
        "goal_field": "question",
        "split": "train",
        "fallback_fields": ["prompt", "input", "text"],
        "description": (
            "SALAD-Bench base set - 21K harmful questions with hierarchical "
            "3-level safety taxonomy"
        ),
    },
    "saladbench_attack": {
        "provider": "huggingface",
        "path": "OpenSafetyLab/Salad-Data",
        "name": "attack_enhanced_set",
        "goal_field": "augq",
        "split": "train",
        "fallback_fields": ["question", "baseq", "prompt", "input"],
        "description": (
            "SALAD-Bench attack-enhanced set - 5K questions augmented with "
            "jailbreak attack methods (GPTFuzzer, etc.)"
        ),
    },
    # =========================================================================
    # ToxicChat - Real-world toxic user prompts
    # Source: https://huggingface.co/datasets/lmsys/toxic-chat
    # Collected from Vicuna online demo, human-annotated
    # ~7% toxic, ~2% jailbreaking attempts
    # Paper: https://arxiv.org/abs/2310.17389
    # =========================================================================
    "toxicchat": {
        "provider": "huggingface",
        "path": "lmsys/toxic-chat",
        "name": "toxicchat0124",
        "goal_field": "user_input",
        "split": "train",
        "fallback_fields": ["prompt", "input", "text"],
        "description": (
            "ToxicChat - 10K real user prompts from Vicuna demo with "
            "human-annotated toxicity and jailbreaking labels"
        ),
    },
    # =========================================================================
    # Discrim-Eval - Discrimination in LM decision-making
    # Source: https://huggingface.co/datasets/Anthropic/discrim-eval
    # 70 decision scenarios × 135 demographic combos (age, gender, race)
    # Available configs: 'explicit', 'implicit'
    # Paper: https://arxiv.org/abs/2312.03689
    # =========================================================================
    "discrim_eval": {
        "provider": "huggingface",
        "path": "Anthropic/discrim-eval",
        "name": "explicit",
        "goal_field": "filled_template",
        "split": "train",
        "fallback_fields": ["prompt", "input", "text"],
        "description": (
            "Discrim-Eval - 9.4K decision prompts testing for discrimination "
            "by race, gender, and age across 70 scenarios (Anthropic)"
        ),
    },
    # =========================================================================
    # Prompt Injections - Injection attack samples
    # Source: https://huggingface.co/datasets/deepset/prompt-injections
    # Binary classification dataset for prompt injection detection
    # =========================================================================
    "prompt_injections": {
        "provider": "huggingface",
        "path": "deepset/prompt-injections",
        "goal_field": "text",
        "split": "train",
        "fallback_fields": ["prompt", "input"],
        "description": (
            "Prompt Injections - 662 prompt injection samples for "
            "injection attack detection and testing (deepset)"
        ),
    },
    # =========================================================================
    # AIR-Bench 2024 - Regulation-aligned safety evaluation
    # Source: https://huggingface.co/datasets/stanford-crfm/air-bench-2024
    # 5,690 prompts mapped to government AI regulation risk categories
    # with hierarchical 4-level taxonomy (cate-idx, l2-name, l3-name, l4-name)
    # From the Inspect Evals framework (UK AISI)
    # Paper: https://arxiv.org/abs/2407.17436
    # =========================================================================
    "airbench": {
        "provider": "huggingface",
        "path": "stanford-crfm/air-bench-2024",
        "goal_field": "prompt",
        "split": "test",
        "fallback_fields": ["input", "text"],
        "description": (
            "AIR-Bench 2024 - 5,690 regulation-aligned malicious prompts "
            "with 4-level risk taxonomy from government AI regulations "
            "(Stanford CRFM, Inspect Evals)"
        ),
    },
    # =========================================================================
    # SOS-Bench - Safety alignment on scientific knowledge
    # Source: https://huggingface.co/datasets/SOSBench/SOSBench
    # 3,000 prompts across 6 high-risk scientific domains:
    # biology, chemistry, pharmacy, physics, psychology, medical
    # From the Inspect Evals framework (UK AISI)
    # Paper: https://arxiv.org/abs/2505.21605
    # =========================================================================
    "sosbench": {
        "provider": "huggingface",
        "path": "SOSBench/SOSBench",
        "goal_field": "goal",
        "split": "train",
        "fallback_fields": ["prompt", "input", "text"],
        "description": (
            "SOS-Bench - 3,000 hazardous science prompts across 6 domains "
            "(biology, chemistry, pharmacy, physics, psychology, medical) "
            "for safety alignment evaluation (Inspect Evals)"
        ),
    },
    # =========================================================================
    # RAG Security - RAG/embedding security evaluation
    # Note: SafeRAG benchmark is under development (arxiv:2501.18636)
    # Using galileo-ai/ragbench as interim general RAG evaluation dataset
    # Source: https://huggingface.co/datasets/galileo-ai/ragbench
    # TODO: Replace with SafeRAG when available on HuggingFace
    # =========================================================================
    "rag_security": {
        "provider": "huggingface",
        "path": "galileo-ai/ragbench",
        "goal_field": "question",
        "split": "train",
        "fallback_fields": ["query", "prompt", "input", "text"],
        "description": (
            "RAGBench - 100K RAG benchmark covering industry-specific domains, "
            "used as interim for RAG security testing (pending SafeRAG release)"
        ),
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
