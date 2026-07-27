# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Static catalog of attack strategies exposed by ``hackagent eval``."""

from typing import Dict

ATTACK_CATALOG: Dict[str, Dict[str, str]] = {
    "advprefix": {
        "label": "AdvPrefix",
        "description": "Adversarial prefix generation pipeline with judge-based evaluation.",
    },
    "baseline": {
        "label": "Baseline",
        "description": "Direct goal submission without transformation (control condition).",
    },
    "static_template": {
        "label": "Static Template",
        "description": "Template-based static template jailbreak attack.",
    },
    "pair": {
        "label": "PAIR",
        "description": "Prompt Automatic Iterative Refinement with attacker/scorer loops.",
    },
    "flipattack": {
        "label": "FlipAttack",
        "description": "Prompt obfuscation via character/word flipping modes.",
    },
    "tap": {
        "label": "TAP",
        "description": "Tree of Attacks with Pruning search attack.",
    },
    "autodan_turbo": {
        "label": "AutoDAN-Turbo",
        "description": "Lifelong jailbreak strategy search with warm-up and retrieval phases.",
    },
    "bon": {
        "label": "BoN",
        "description": "Best-of-N augmentation search with inline judge evaluation.",
    },
    "cipherchat": {
        "label": "CipherChat",
        "description": "Cipher-based prompt transformation with optional demonstrations.",
    },
    "h4rm3l": {
        "label": "h4rm3l",
        "description": "Composable decorator-program attack chaining multiple obfuscations.",
    },
    "pap": {
        "label": "PAP",
        "description": "Persuasive Adversarial Prompts using persuasion-technique taxonomies.",
    },
    "mml": {
        "label": "MML",
        "description": "Multi-Modal Linkage attack encoding harmful prompts into images for VLMs.",
    },
    "fc": {
        "label": "FC-Attack",
        "description": "FC-Attack: auto-generated flowchart images to jailbreak VLMs.",
    },
    "tfc": {
        "label": "tFC-Attack",
        "description": "tFC-Attack: text-only flowchart encoding attack for any LLM (DOT, Mermaid, TikZ, PlantUML, ASCII).",
    },
}
