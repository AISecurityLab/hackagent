# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
FC-Attack (FlowChart Attack) implementation.

Provides two attack classes:

- ``FCAttack`` — Image-based multimodal attack (faithful to the paper).
  Renders flowchart images and sends them to Vision-Language Models.
- ``tFCAttack`` — Text-only variant. Encodes flowcharts as graph
  description languages (DOT, Mermaid, TikZ, PlantUML, ASCII) for any LLM.

Based on: Zhang et al., "FC-Attack: Jailbreaking Multimodal Large
Language Models via Auto-Generated Flowcharts" (EMNLP 2025 Findings)
https://arxiv.org/abs/2502.21059

The shared logic (step decomposition, rendering, evaluation) is in the
``generation``, ``flowchart_renderer``, and ``evaluation`` modules.
"""

import copy
import logging
from typing import Any, Dict, List, Optional

from hackagent.attacks.techniques.base import BaseAttack
from hackagent.attacks.shared.tui import with_tui_logging
from hackagent.attacks.techniques.config import DEFAULT_JUDGE_IDENTIFIER
from hackagent.router.router import AgentRouter
from hackagent.server.client import AuthenticatedClient

from . import evaluation
from .generation import execute_fc, execute_tfc
from .config import DEFAULT_FC_CONFIG, DEFAULT_TFC_CONFIG


def _recursive_update(target_dict, source_dict):
    """
    Recursively updates a target dictionary with values from a source dictionary.
    Nested dictionaries are merged; other values are overwritten with a deep copy.
    Special internal keys (starting with '_') are passed by reference without copying.
    """
    for key, source_value in source_dict.items():
        target_value = target_dict.get(key)
        if isinstance(source_value, dict) and isinstance(target_value, dict):
            _recursive_update(target_value, source_value)
        elif key.startswith("_"):
            target_dict[key] = source_value
        else:
            target_dict[key] = copy.deepcopy(source_value)


class FCAttack(BaseAttack):
    """
    FC-Attack — Flowchart-based jailbreak attack for Vision-Language Models.

    Implements the FC-Attack technique from:
        Zhang et al., "FC-Attack: Jailbreaking Multimodal Large Language
        Models via Auto-Generated Flowcharts" (EMNLP 2025 Findings)
        https://arxiv.org/abs/2502.21059

    This attack decomposes harmful prompts into step descriptions,
    renders them as flowchart images in various layouts, then sends
    the images to a VLM with a carefully crafted text prompt that
    induces the model to analyze and complete the harmful content.

    Layout modes (set via ``config["fc_params"]["layout"]``):
        vertical
            Steps flow top-to-bottom in a single vertical column.
        horizontal
            Steps flow left-to-right in a single horizontal row.
        s_shaped
            Steps flow in an S-shaped (serpentine) path, alternating
            direction on each row for compact display.

    Attributes:
        layout: Active layout mode, read from config.
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        client: Optional[AuthenticatedClient] = None,
        agent_router: Optional[AgentRouter] = None,
    ):
        """
        Initialize FlowchartAttack with configuration.

        Args:
            config: Optional dictionary containing parameters to override
                :data:`DEFAULT_FC_CONFIG`.
            client: AuthenticatedClient instance passed from the orchestrator.
            agent_router: AgentRouter instance for the target model.

        Raises:
            ValueError: If ``client`` or ``agent_router`` is ``None``.
        """
        if client is None:
            raise ValueError("AuthenticatedClient must be provided to FCAttack.")
        if agent_router is None:
            raise ValueError(
                "Victim AgentRouter instance must be provided to FCAttack."
            )

        # Merge config with defaults
        current_config = copy.deepcopy(DEFAULT_FC_CONFIG)
        if config:
            _recursive_update(current_config, config)

        self.logger = logging.getLogger("hackagent.attacks.FC")
        super().__init__(current_config, client, agent_router)

    def _setup(self) -> None:
        """Run standard setup then initialise algorithm-specific state."""
        super()._setup()
        self._setup_algorithm()
        self._warn_if_not_vlm()

    def _setup_algorithm(self) -> None:
        """Read flowchart parameters from config into instance attributes."""
        fc_params = self.config.get("fc_params", {})
        self.layout = fc_params.get("layout", "vertical")

    def _warn_if_not_vlm(self) -> None:
        """Emit a warning if the target model does not appear to be a VLM."""
        _VISION_PATTERNS = (
            "vision",
            "vlm",
            "vl",
            "gpt-4o",
            "gpt-4-turbo",
            "gpt-4-vision",
            "gemini",
            "claude-3",
            "qwen-vl",
            "qwen2-vl",
            "qwen2.5-vl",
            "qwen3-vl",
            "qwen3.5-vl",
            "llava",
            "internvl",
            "cogvlm",
            "pixtral",
            "phi-3-vision",
            "phi-3.5-vision",
            "phi-4-multimodal",
        )

        model_name = None
        try:
            metadata = self.agent_router.backend_agent.metadata
            if isinstance(metadata, dict):
                model_name = metadata.get("name") or metadata.get("model_name")
        except AttributeError:
            pass

        if model_name is None:
            self.logger.warning(
                "FC-Attack requires a Vision-Language Model (VLM) that supports "
                "image inputs. Could not determine the target model name — ensure "
                "the target supports multimodal (image_url) messages."
            )
            return

        model_lower = model_name.lower()
        if not any(pattern in model_lower for pattern in _VISION_PATTERNS):
            self.logger.warning(
                f"FC-Attack requires a Vision-Language Model (VLM) that supports "
                f"image inputs. The target model '{model_name}' does not appear to "
                f"be a VLM. If the model does support vision, you can ignore this "
                f"warning."
            )

    # ------------------------------------------------------------------
    # Pipeline definition
    # ------------------------------------------------------------------

    def _validate_config(self):
        """Validate the provided configuration dictionary."""
        super()._validate_config()

        required_keys = [
            "attack_type",
            "fc_params",
            "goals",
            "output_dir",
        ]

        missing = [k for k in required_keys if k not in self.config]
        if missing:
            raise ValueError(
                f"Configuration dictionary missing required keys: {', '.join(missing)}"
            )

        # Validate layout
        fc_params = self.config.get("fc_params", {})
        valid_layouts = ["vertical", "horizontal", "tortuous", "s_shaped"]
        layout = fc_params.get("layout", "vertical")

        if layout not in valid_layouts:
            raise ValueError(f"layout must be one of {valid_layouts}, got '{layout}'")

    def _get_pipeline_steps(self) -> List[Dict]:
        """Define the two-stage attack pipeline."""
        return [
            {
                "name": "Generation: Render Flowcharts and Execute FC-Attack",
                "function": execute_fc,
                "step_type_enum": "GENERATION",
                "config_keys": [
                    "batch_size",
                    "max_tokens",
                    "fc_params",
                    "step_generator",
                    "_run_id",
                    "_backend",
                    "_client",
                    "_tracker",
                ],
                "input_data_arg_name": "goals",
                "required_args": ["logger", "agent_router", "config"],
            },
            {
                "name": "Evaluation: Evaluate Responses with LLM Judge",
                "function": evaluation.execute,
                "step_type_enum": "EVALUATION",
                "config_keys": [
                    "fc_params",
                    "_run_id",
                    "_backend",
                    "_client",
                    "_tracker",
                    "judges",
                    "batch_size_judge",
                    "max_tokens_eval",
                    "filter_len",
                    "judge_timeout",
                    "judge_temperature",
                    "max_judge_retries",
                ],
                "input_data_arg_name": "input_data",
                "required_args": ["logger", "config", "client"],
            },
        ]

    @with_tui_logging(logger_name="hackagent.attacks", level=logging.INFO)
    def run(self, goals: List[str]) -> List[Dict]:
        """
        Execute the full FC-Attack pipeline.

        Args:
            goals: A list of goal strings to test.

        Returns:
            List of dictionaries containing evaluation results,
            or empty list if no goals provided.
        """
        if not goals:
            return []

        fc_params = self.config.get("fc_params", {})
        goal_metadata = {
            "layout": fc_params.get("layout", "vertical"),
            "num_steps": fc_params.get("num_steps", 5),
            "judge": fc_params.get("judge", DEFAULT_JUDGE_IDENTIFIER),
        }

        coordinator = self._initialize_coordinator(
            attack_type="fc",
            goals=goals,
            initial_metadata=goal_metadata,
        )

        pipeline_steps = self._get_pipeline_steps()
        start_step = self.config.get("start_step", 1) - 1

        if coordinator.goal_tracker:
            self.config["_tracker"] = coordinator.goal_tracker

        try:
            results = self._execute_pipeline(
                pipeline_steps, goals, start_step=start_step
            )

            coordinator.finalize_all_goals(results)
            coordinator.log_summary()
            coordinator.finalize_pipeline(results)

            return results if results is not None else []

        except Exception:
            coordinator.finalize_on_error("FC-Attack pipeline failed with exception")
            raise


class tFCAttack(BaseAttack):
    """
    Text-only flowchart attack for any LLM.

    Encodes harmful prompts as graph description languages (DOT, Mermaid,
    TikZ, PlantUML, ASCII) and sends them as text to the target model.
    This tests whether structured/code-formatted harmful content can
    bypass natural-language safety filters without requiring vision.

    Unlike :class:`FCAttack`, this does NOT render images and works
    with any text LLM (no VLM required).

    Attributes:
        layout: Active layout mode, read from config.
        text_format: Graph description format (dot, mermaid, tikz, plantuml, ascii).
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        client: Optional[AuthenticatedClient] = None,
        agent_router: Optional[AgentRouter] = None,
    ):
        if client is None:
            raise ValueError("AuthenticatedClient must be provided to tFCAttack.")
        if agent_router is None:
            raise ValueError(
                "Victim AgentRouter instance must be provided to tFCAttack."
            )

        current_config = copy.deepcopy(DEFAULT_TFC_CONFIG)
        if config:
            _recursive_update(current_config, config)

        self.logger = logging.getLogger("hackagent.attacks.tFC")
        super().__init__(current_config, client, agent_router)

    def _setup(self) -> None:
        """Run standard setup then initialise algorithm-specific state."""
        super()._setup()
        self._setup_algorithm()

    def _setup_algorithm(self) -> None:
        """Read tFC parameters from config into instance attributes."""
        tfc_params = self.config.get("tfc_params", {})
        self.layout = tfc_params.get("layout", "vertical")
        self.text_format = tfc_params.get("text_format", "dot")

    def _validate_config(self):
        """Validate the provided configuration dictionary."""
        super()._validate_config()

        required_keys = [
            "attack_type",
            "tfc_params",
            "goals",
            "output_dir",
        ]

        missing = [k for k in required_keys if k not in self.config]
        if missing:
            raise ValueError(
                f"Configuration dictionary missing required keys: {', '.join(missing)}"
            )

        tfc_params = self.config.get("tfc_params", {})
        valid_layouts = ["vertical", "horizontal", "tortuous", "s_shaped"]
        layout = tfc_params.get("layout", "vertical")
        if layout not in valid_layouts:
            raise ValueError(f"layout must be one of {valid_layouts}, got '{layout}'")

        valid_formats = ["dot", "mermaid", "tikz", "plantuml", "ascii"]
        text_format = tfc_params.get("text_format", "dot")
        if text_format not in valid_formats:
            raise ValueError(
                f"text_format must be one of {valid_formats}, got '{text_format}'"
            )

    def _get_pipeline_steps(self) -> List[Dict]:
        """Define the two-stage attack pipeline."""
        return [
            {
                "name": "Generation: Render Text Flowcharts and Execute tFC-Attack",
                "function": execute_tfc,
                "step_type_enum": "GENERATION",
                "config_keys": [
                    "batch_size",
                    "max_tokens",
                    "tfc_params",
                    "step_generator",
                    "_run_id",
                    "_backend",
                    "_client",
                    "_tracker",
                ],
                "input_data_arg_name": "goals",
                "required_args": ["logger", "agent_router", "config"],
            },
            {
                "name": "Evaluation: Evaluate Responses with LLM Judge",
                "function": evaluation.execute,
                "step_type_enum": "EVALUATION",
                "config_keys": [
                    "tfc_params",
                    "_run_id",
                    "_backend",
                    "_client",
                    "_tracker",
                    "judges",
                    "batch_size_judge",
                    "max_tokens_eval",
                    "filter_len",
                    "judge_timeout",
                    "judge_temperature",
                    "max_judge_retries",
                ],
                "input_data_arg_name": "input_data",
                "required_args": ["logger", "config", "client"],
            },
        ]

    @with_tui_logging(logger_name="hackagent.attacks", level=logging.INFO)
    def run(self, goals: List[str]) -> List[Dict]:
        """
        Execute the full text-only flowchart attack pipeline.

        Args:
            goals: A list of goal strings to test.

        Returns:
            List of dictionaries containing evaluation results,
            or empty list if no goals provided.
        """
        if not goals:
            return []

        tfc_params = self.config.get("tfc_params", {})
        goal_metadata = {
            "layout": tfc_params.get("layout", "vertical"),
            "num_steps": tfc_params.get("num_steps", 5),
            "text_format": tfc_params.get("text_format", "dot"),
            "judge": tfc_params.get("judge", DEFAULT_JUDGE_IDENTIFIER),
        }

        coordinator = self._initialize_coordinator(
            attack_type="tFC",
            goals=goals,
            initial_metadata=goal_metadata,
        )

        pipeline_steps = self._get_pipeline_steps()
        start_step = self.config.get("start_step", 1) - 1

        if coordinator.goal_tracker:
            self.config["_tracker"] = coordinator.goal_tracker

        try:
            results = self._execute_pipeline(
                pipeline_steps, goals, start_step=start_step
            )

            coordinator.finalize_all_goals(results)
            coordinator.log_summary()
            coordinator.finalize_pipeline(results)

            return results if results is not None else []

        except Exception:
            coordinator.finalize_on_error("tFC pipeline failed with exception")
            raise
