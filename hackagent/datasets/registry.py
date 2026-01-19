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
Registry and factory functions for dataset providers.

This module provides the main entry point for loading goals from various sources.
"""

import logging
from typing import Any, Dict, List, Optional, Type

from hackagent.datasets.base import DatasetProvider
from hackagent.datasets.presets import PRESETS, get_preset, list_presets

logger = logging.getLogger(__name__)

# Provider registry
_PROVIDERS: Dict[str, Type[DatasetProvider]] = {}


def register_provider(name: str, provider_class: Type[DatasetProvider]) -> None:
    """
    Register a dataset provider.

    Args:
        name: The provider name.
        provider_class: The provider class.
    """
    _PROVIDERS[name.lower()] = provider_class


def get_provider(name: str, config: Dict[str, Any]) -> DatasetProvider:
    """
    Get a dataset provider instance by name.

    Args:
        name: The provider name (e.g., "huggingface", "file").
        config: Provider configuration dictionary.

    Returns:
        Configured DatasetProvider instance.

    Raises:
        ValueError: If the provider is not found.
    """
    name_lower = name.lower()

    if name_lower not in _PROVIDERS:
        available = ", ".join(sorted(_PROVIDERS.keys()))
        raise ValueError(
            f"Unknown dataset provider: '{name}'. Available providers: {available}"
        )

    return _PROVIDERS[name_lower](config)


def load_goals(
    # Preset-based loading
    preset: Optional[str] = None,
    # Direct provider loading
    provider: Optional[str] = None,
    path: Optional[str] = None,
    goal_field: Optional[str] = None,
    split: Optional[str] = None,
    name: Optional[str] = None,
    # Common options
    limit: Optional[int] = None,
    shuffle: bool = False,
    seed: Optional[int] = None,
    # Extra config
    **kwargs,
) -> List[str]:
    """
    Load attack goals from a dataset source.

    This is the main entry point for loading goals. It supports three modes:
    1. Preset mode: Use a pre-configured dataset by name
    2. Provider mode: Directly specify provider and dataset details
    3. Config mode: Pass a full configuration dictionary

    Args:
        preset: Name of a pre-configured dataset preset (e.g., "agentharm", "strongreject").
        provider: Provider type ("huggingface" or "file").
        path: Dataset path (HuggingFace dataset ID or file path).
        goal_field: Field name containing the goal text.
        split: Dataset split to use (for HuggingFace).
        name: Dataset configuration name (for HuggingFace datasets with multiple configs).
        limit: Maximum number of goals to return.
        shuffle: Whether to shuffle before selecting.
        seed: Random seed for shuffling.
        **kwargs: Additional provider-specific configuration.

    Returns:
        List of goal strings.

    Examples:
        # Using a preset
        goals = load_goals(preset="agentharm", limit=50)

        # Using HuggingFace directly
        goals = load_goals(
            provider="huggingface",
            path="ai-safety-institute/AgentHarm",
            name="harmful",
            goal_field="prompt",
            split="test_public",
            limit=100
        )

        # Using a local file
        goals = load_goals(
            provider="file",
            path="./my_goals.json",
            goal_field="objective"
        )

    Raises:
        ValueError: If neither preset nor provider is specified.
    """
    # Build configuration
    if preset:
        # Use preset configuration
        config = get_preset(preset)
        provider_name = config.pop("provider", "huggingface")

        # Override preset with any explicit arguments
        if path:
            config["path"] = path
        if goal_field:
            config["goal_field"] = goal_field
        if split:
            config["split"] = split
        if name:
            config["name"] = name

        # Add any extra kwargs
        config.update(kwargs)

    elif provider:
        # Build config from arguments
        provider_name = provider
        config = {
            "path": path,
            "goal_field": goal_field or "input",
            **kwargs,
        }
        if split:
            config["split"] = split
        if name:
            config["name"] = name

    else:
        raise ValueError(
            "Either 'preset' or 'provider' must be specified. "
            f"Available presets: {', '.join(sorted(PRESETS.keys()))}"
        )

    # Get provider instance
    provider_instance = get_provider(provider_name, config)

    # Load and return goals
    return provider_instance.load_goals(
        limit=limit,
        shuffle=shuffle,
        seed=seed,
    )


def load_goals_from_config(config: Dict[str, Any]) -> List[str]:
    """
    Load goals from a configuration dictionary.

    This function is designed to be called from the AttackOrchestrator
    when a 'dataset' key is present in the attack configuration.

    Args:
        config: Dataset configuration dictionary with keys:
            - preset (str, optional): Preset name
            - provider (str, optional): Provider type
            - path (str, optional): Dataset path
            - goal_field (str, optional): Field containing goals
            - split (str, optional): Dataset split
            - name (str, optional): Dataset config name
            - limit (int, optional): Max goals to load
            - shuffle (bool, optional): Shuffle before selecting
            - seed (int, optional): Random seed

    Returns:
        List of goal strings.

    Example config:
        {
            "preset": "agentharm",
            "limit": 100,
            "shuffle": True
        }

        Or:

        {
            "provider": "huggingface",
            "path": "ai-safety-institute/AgentHarm",
            "goal_field": "prompt",
            "split": "test_public",
            "limit": 50
        }
    """
    return load_goals(**config)


# Register built-in providers on import
def _register_builtin_providers():
    """Register the built-in dataset providers."""
    from hackagent.datasets.providers.file import FileDatasetProvider
    from hackagent.datasets.providers.huggingface import HuggingFaceDatasetProvider

    register_provider("huggingface", HuggingFaceDatasetProvider)
    register_provider("hf", HuggingFaceDatasetProvider)  # Alias
    register_provider("file", FileDatasetProvider)
    register_provider("local", FileDatasetProvider)  # Alias


_register_builtin_providers()


# Re-export preset utilities
__all__ = [
    "get_provider",
    "register_provider",
    "load_goals",
    "load_goals_from_config",
    "get_preset",
    "list_presets",
    "PRESETS",
]
