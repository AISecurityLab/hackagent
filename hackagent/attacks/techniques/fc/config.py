# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Configuration for FC-Attack.

Provides both the plain-dict ``DEFAULT_FC_CONFIG`` (used internally by
:class:`~hackagent.attacks.techniques.fc.attack.FCAttack`) and
typed Pydantic models for structured configuration.

Layout Modes
------------
vertical
    Steps flow top-to-bottom in a single vertical column.
horizontal
    Steps flow left-to-right in a single horizontal row.
s_shaped
    Steps flow in an S-shaped (serpentine/tortuous) path, alternating
    direction on each row for compact display.
"""

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from hackagent.attacks.techniques.config import (
    DEFAULT_CONFIG_BASE,
    DEFAULT_LOCAL_AGENT_TYPE,
    DEFAULT_LOCAL_MODEL_ENDPOINT,
    ConfigBase,
)

DEFAULT_STEP_GENERATOR_IDENTIFIER = "gemma3:4b"


DEFAULT_FC_CONFIG: Dict[str, Any] = {
    **DEFAULT_CONFIG_BASE,
    "attack_type": "fc",
    "fc_params": {
        # Layout: vertical, horizontal, tortuous (S-shaped)
        "layout": "vertical",
        # Graphviz DPI (resolution of rendered PNG)
        "dpi": 600,
        # Step generation settings
        "num_steps": 6,
        # Whether to include partial/truncated last step to induce completion
        "truncate_last_step": True,
    },
    # Step generator model configuration (decomposes goals into steps)
    # Set to None to use built-in heuristic decomposition.
    "step_generator": None,
}


DEFAULT_TFC_CONFIG: Dict[str, Any] = {
    **DEFAULT_CONFIG_BASE,
    "attack_type": "tFC",
    "tfc_params": {
        # Layout: vertical, horizontal, tortuous (S-shaped)
        "layout": "vertical",
        # Step generation settings
        "num_steps": 6,
        # Whether to include partial/truncated last step to induce completion
        "truncate_last_step": True,
        # Text format: dot, mermaid, tikz, plantuml, ascii
        "text_format": "dot",
    },
    # Step generator model configuration (decomposes goals into steps)
    # Set to None to use built-in heuristic decomposition.
    "step_generator": None,
}


class StepGeneratorConfig(BaseModel):
    """Configuration for the step generator LLM.

    Used to decompose harmful goals into numbered step descriptions
    before rendering them as flowcharts.

    Attributes:
        identifier: Model identifier (e.g. ``"gpt-4"``).
        endpoint: API endpoint URL.
        agent_type: Agent adapter type (e.g. ``"OPENAI_SDK"``, ``"OLLAMA"``).
        api_key: Optional API key for the model provider.
        max_tokens: Maximum output tokens for step generation.
        temperature: Sampling temperature.
    """

    model_config = ConfigDict(extra="allow", validate_assignment=True)

    identifier: str = DEFAULT_STEP_GENERATOR_IDENTIFIER
    endpoint: str = DEFAULT_LOCAL_MODEL_ENDPOINT
    agent_type: str = DEFAULT_LOCAL_AGENT_TYPE
    api_key: Optional[str] = None
    max_tokens: int = 512
    temperature: float = 0.3


class FCParams(BaseModel):
    """Hyperparameters controlling the FC-Attack flowchart image generation.

    Attributes:
        layout: Flowchart layout mode. One of ``"vertical"`` (top-to-bottom),
            ``"horizontal"`` (left-to-right), or ``"tortuous"`` (S-shaped).
            ``"s_shaped"`` is accepted as an alias for ``"tortuous"``.
        dpi: Resolution (dots-per-inch) for Graphviz rendering.
        num_steps: Number of steps to decompose the goal into.
        truncate_last_step: Whether to truncate the last step to induce
            the target model to complete the harmful content.
    """

    layout: Literal["vertical", "horizontal", "tortuous", "s_shaped"] = "vertical"
    dpi: int = Field(default=600, ge=72, le=1200)
    num_steps: int = Field(default=6, ge=2, le=15)
    truncate_last_step: bool = True


class tFCParams(BaseModel):
    """Hyperparameters controlling the text-only flowchart attack.

    Attributes:
        layout: Flowchart layout mode (affects text serialization structure).
        text_format: Graph description format to use.
        num_steps: Number of steps to decompose the goal into.
        truncate_last_step: Whether to truncate the last step to induce
            the target model to complete the harmful content.
    """

    layout: Literal["vertical", "horizontal", "tortuous", "s_shaped"] = "vertical"
    text_format: Literal["dot", "mermaid", "tikz", "plantuml", "ascii"] = "dot"
    num_steps: int = Field(default=6, ge=2, le=15)
    truncate_last_step: bool = True


class FCConfig(ConfigBase):
    """Complete FC-Attack configuration for use with :meth:`HackAgent.hack`.

    Attributes:
        attack_type: Always ``"fc"`` (required by the orchestrator).
        fc_params: Flowchart generation hyperparameters.
        step_generator: Optional step generator model config. When ``None``,
            a built-in heuristic decomposition is used instead of an LLM.
    """

    attack_type: str = "fc"
    output_dir: str = "./logs/fc"
    judges: List[Dict[str, Any]] = Field(default_factory=list)
    fc_params: FCParams = Field(default_factory=FCParams)
    step_generator: Optional[Dict[str, Any]] = None

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> "FCConfig":
        """Create a :class:`FCConfig` from a plain dictionary."""
        filtered_config = {
            key: value for key, value in config_dict.items() if key in cls.model_fields
        }
        return cls.model_validate(filtered_config)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return self.model_dump()


class tFCConfig(ConfigBase):
    """Configuration for the text-only flowchart attack.

    Attributes:
        attack_type: Always ``"tFC"`` (required by the orchestrator).
        tfc_params: Text flowchart generation hyperparameters.
        step_generator: Optional step generator model config. When ``None``,
            a built-in heuristic decomposition is used instead of an LLM.
    """

    attack_type: str = "tFC"
    output_dir: str = "./logs/tFC"
    judges: List[Dict[str, Any]] = Field(default_factory=list)
    tfc_params: tFCParams = Field(default_factory=tFCParams)
    step_generator: Optional[Dict[str, Any]] = None

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> "tFCConfig":
        """Create a :class:`tFCConfig` from a plain dictionary."""
        filtered_config = {
            key: value for key, value in config_dict.items() if key in cls.model_fields
        }
        return cls.model_validate(filtered_config)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return self.model_dump()
