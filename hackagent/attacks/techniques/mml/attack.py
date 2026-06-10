# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
MML (Multi-Modal Linkage) attack implementation.

Encodes harmful prompts into images using visual transformations (word
replacement, mirroring, rotation, Base64 encoding), then constructs
multimodal prompts that instruct a Vision-Language Model to decode and
act on the embedded content.

Based on: https://arxiv.org/abs/2412.00473

The ``MMLAttack`` class serves as the HackAgent pipeline orchestrator
(``BaseAttack`` subclass). The encoding and prompt construction logic
is factored into ``image_encoder`` and ``prompts`` modules.

Result Tracking:
    Uses TrackingCoordinator to manage both pipeline-level StepTracker
    and per-goal Tracker. The coordinator handles goal lifecycle,
    crash-safe finalization, and data enrichment (result_id injection).
"""

import copy
import logging
from typing import Any, Dict, List, Optional

from hackagent.attacks.techniques.base import BaseAttack
from hackagent.attacks.shared.tui import with_tui_logging
from hackagent.attacks.techniques.config import DEFAULT_JUDGE_IDENTIFIER
from hackagent.router.router import AgentRouter
from hackagent.server.client import AuthenticatedClient

from . import evaluation, generation
from .config import DEFAULT_MML_CONFIG


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


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


class MMLAttack(BaseAttack):
    """
    MML — Multi-Modal Linkage attack for Vision-Language Models.

    Implements the MML technique from:
        Wang et al., "Jailbreak Large Vision-Language Models Through
        Multi-Modal Linkage" (2024)
        https://arxiv.org/abs/2412.00473

    This attack encodes harmful prompts into images using visual
    transformations and pairs them with carefully crafted text prompts
    that guide the VLM to decode and follow the hidden instructions.

    Encoding modes (set via ``config["mml_params"]["encoding_mode"]``):
        word_replacement
            Replaces key words in the prompt with innocuous substitutes,
            renders to image, and provides a replacement dictionary in
            the text prompt for the model to reconstruct the original.
        mirror
            Renders the harmful prompt as text in an image, then flips
            the image horizontally. The text prompt instructs the model
            to mentally mirror the image.
        rotate
            Renders the harmful prompt as text in an image, then rotates
            180 degrees. The text prompt instructs the model to mentally
            rotate the image.
        base64
            Encodes the prompt text in Base64 and renders the encoded
            string in an image. The text prompt instructs the model to
            decode the Base64 content.
        mixed
            Combines word replacement, horizontal mirroring, and 180-degree
            rotation. Renders the replaced text to an image, then applies
            both spatial transformations.

    Prompt styles (set via ``config["mml_params"]["prompt_style"]``):
        game
            Uses a villain's lair game scenario to frame the request.
        control
            Uses a neutral list-filling prompt.

    Attributes:
        encoding_mode: Active encoding mode, read from config.
        prompt_style: Active prompt framing style.
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        client: Optional[AuthenticatedClient] = None,
        agent_router: Optional[AgentRouter] = None,
    ):
        """
        Initialize MMLAttack with configuration.

        Args:
            config: Optional dictionary containing parameters to override
                :data:`~hackagent.attacks.techniques.mml.config.DEFAULT_MML_CONFIG`.
            client: AuthenticatedClient instance passed from the orchestrator.
            agent_router: AgentRouter instance for the target model.

        Raises:
            ValueError: If ``client`` or ``agent_router`` is ``None``.
        """
        if client is None:
            raise ValueError("AuthenticatedClient must be provided to MMLAttack.")
        if agent_router is None:
            raise ValueError(
                "Victim AgentRouter instance must be provided to MMLAttack."
            )

        # Merge config with defaults
        current_config = copy.deepcopy(DEFAULT_MML_CONFIG)
        if config:
            _recursive_update(current_config, config)

        # Set logger name for hierarchical logging (TUI support)
        self.logger = logging.getLogger("hackagent.attacks.mml")

        # Call parent - handles run_id, run_dir, validation, setup
        super().__init__(current_config, client, agent_router)

    def _setup(self) -> None:
        """Run standard setup then initialise algorithm-specific state."""
        super()._setup()
        self._setup_algorithm()
        self._warn_if_not_vlm()

    def _setup_algorithm(self) -> None:
        """Read MML parameters from config into instance attributes."""
        mml_params = self.config.get("mml_params", {})
        self.encoding_mode = mml_params.get("encoding_mode", "word_replacement")
        self.prompt_style = mml_params.get("prompt_style", "game")

    def _warn_if_not_vlm(self) -> None:
        """Emit a warning if the target model does not appear to be a VLM."""
        # Known vision-capable model name patterns
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
                "MML attack requires a Vision-Language Model (VLM) that supports "
                "image inputs. Could not determine the target model name — ensure "
                "the target supports multimodal (image_url) messages."
            )
            return

        model_lower = model_name.lower()
        if not any(pattern in model_lower for pattern in _VISION_PATTERNS):
            self.logger.warning(
                f"MML attack requires a Vision-Language Model (VLM) that supports "
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
            "mml_params",
            "goals",
            "output_dir",
        ]

        missing = [k for k in required_keys if k not in self.config]
        if missing:
            raise ValueError(
                f"Configuration dictionary missing required keys: {', '.join(missing)}"
            )

        # Validate encoding_mode
        mml_params = self.config.get("mml_params", {})
        valid_modes = ["word_replacement", "mirror", "rotate", "base64", "mixed"]
        encoding_mode = mml_params.get("encoding_mode", "word_replacement")

        if encoding_mode not in valid_modes:
            raise ValueError(
                f"encoding_mode must be one of {valid_modes}, got '{encoding_mode}'"
            )

    def _get_pipeline_steps(self) -> List[Dict]:
        """Define the two-stage attack pipeline."""
        return [
            {
                "name": "Generation: Encode and Execute MML Prompts",
                "function": generation.execute,
                "step_type_enum": "GENERATION",
                "config_keys": [
                    "batch_size",
                    "max_tokens",
                    "mml_params",
                    "_run_id",
                    "_backend",
                    "_client",
                    "_tracker",
                ],
                "input_data_arg_name": "goals",
                "required_args": ["logger", "agent_router", "config"],
            },
            {
                "name": "Evaluation: Evaluate Responses with Dict + LLM Judge",
                "function": evaluation.execute,
                "step_type_enum": "EVALUATION",
                "config_keys": [
                    "mml_params",
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
        Execute the full MML attack pipeline.

        Uses a split-phase approach: the coordinator is created with
        goal Results upfront so elapsed_s covers the full lifecycle.

        Args:
            goals: A list of goal strings to test.

        Returns:
            List of dictionaries containing evaluation results,
            or empty list if no goals provided.
        """
        if not goals:
            return []

        mml_params = self.config.get("mml_params", {})
        goal_metadata = {
            "encoding_mode": mml_params.get("encoding_mode", "word_replacement"),
            "prompt_style": mml_params.get("prompt_style", "game"),
            "judge": mml_params.get("judge", DEFAULT_JUDGE_IDENTIFIER),
        }

        # Initialize goal contexts upfront so goal elapsed_s covers the full
        # lifecycle (generation + evaluation).
        coordinator = self._initialize_coordinator(
            attack_type="mml",
            goals=goals,
            initial_metadata=goal_metadata,
        )

        pipeline_steps = self._get_pipeline_steps()
        start_step = self.config.get("start_step", 1) - 1

        # Keep tracker in config for generation/evaluation compatibility paths.
        if coordinator.goal_tracker:
            self.config["_tracker"] = coordinator.goal_tracker

        try:
            # Run full pipeline.
            results = self._execute_pipeline(
                pipeline_steps, goals, start_step=start_step
            )

            # Finalize goal results via coordinator
            coordinator.finalize_all_goals(results)

            # Log summary
            coordinator.log_summary()

            # Finalize pipeline-level tracking
            coordinator.finalize_pipeline(results)

            return results if results is not None else []

        except Exception:
            # Crash-safe: mark all unfinalized goals as failed
            coordinator.finalize_on_error("MML pipeline failed with exception")
            raise
