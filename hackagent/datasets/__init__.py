# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Dataset providers for HackAgent.

This module provides a flexible system for loading attack goals from various sources:
- HuggingFace datasets (e.g., AgentHarm, StrongREJECT)
- Local files (CSV, JSON, JSONL)
- Pre-configured safety evaluation presets

Example usage:
    from hackagent.datasets import load_goals, list_presets

    # List available presets
    presets = list_presets()

    # Using a preset
    goals = load_goals(preset="agentharm", limit=50)

    # Using HuggingFace directly
    goals = load_goals(
        provider="huggingface",
        path="ai-safety-institute/AgentHarm",
        name="harmful",
        goal_field="prompt",
        split="test_public"
    )

    # Using a local file
    goals = load_goals(provider="file", path="./my_goals.json", goal_field="goal")
"""

from hackagent.datasets.base import DatasetProvider
from hackagent.datasets.presets import PRESETS, get_preset, list_presets
from hackagent.datasets.registry import (
    get_provider,
    load_goals,
    load_goals_from_config,
    register_provider,
)

__all__ = [
    "DatasetProvider",
    "PRESETS",
    "get_preset",
    "get_provider",
    "list_presets",
    "load_goals",
    "load_goals_from_config",
    "register_provider",
]
