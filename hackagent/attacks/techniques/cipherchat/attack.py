# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""CipherChat attack implementation.

Based on RobustNLP/CipherChat (MIT):
https://github.com/RobustNLP/CipherChat

Paper: "GPT-4 Is Too Smart To Be Safe: Stealthy Chat with LLMs via Cipher"
(ICLR 2024)
"""

import copy
import logging
from typing import Any, Dict, List, Optional

from hackagent.attacks.ports import RunContext
from hackagent.attacks.techniques.base import BaseAttack
from hackagent.attacks.types import AttackResult, rows_to_attack_results
from hackagent.storage.store import Store
from hackagent.attacks._lib.llm_router import LLMRouter


from . import generation
from .config import DEFAULT_CIPHERCHAT_CONFIG
from .encode_experts import encode_expert_dict
from .prompts_and_demonstrations import demonstration_dict


def _recursive_update(target_dict: Dict[str, Any], source_dict: Dict[str, Any]) -> None:
    """Recursively merge source into target preserving internal references."""
    for key, source_value in source_dict.items():
        target_value = target_dict.get(key)
        if isinstance(source_value, dict) and isinstance(target_value, dict):
            _recursive_update(target_value, source_value)
        elif key.startswith("_"):
            target_dict[key] = source_value
        else:
            target_dict[key] = copy.deepcopy(source_value)


class CipherChatAttack(BaseAttack):
    """CipherChat jailbreak attack using encoded non-natural language prompts."""

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        ctx_or_client: Any = None,
        agent_router: Optional[LLMRouter] = None,
        *,
        ctx: Optional[RunContext] = None,
        client: Optional[Store] = None,
    ):
        if ctx is None and isinstance(ctx_or_client, RunContext):
            ctx = ctx_or_client
        resolved_client = (
            client
            if client is not None
            else (None if isinstance(ctx_or_client, RunContext) else ctx_or_client)
        )
        if ctx is None:
            if resolved_client is None:
                raise ValueError("A storage backend must be provided")
            if agent_router is None:
                raise ValueError("LLMRouter must be provided")
            client = resolved_client

        current_config = copy.deepcopy(DEFAULT_CIPHERCHAT_CONFIG)
        if config:
            _recursive_update(current_config, config)

        self.logger = logging.getLogger("hackagent.attacks.cipherchat")
        if ctx is not None:
            super().__init__(current_config, ctx)
        else:
            super().__init__(current_config, client, agent_router)

    def _validate_config(self) -> None:
        super()._validate_config()

        required_keys = ["attack_type", "cipherchat_params", "output_dir"]
        missing = [k for k in required_keys if k not in self.config]
        if missing:
            raise ValueError(f"Missing required config keys: {', '.join(missing)}")

        params = self.config.get("cipherchat_params", {})
        if not isinstance(params, dict):
            raise ValueError("cipherchat_params must be a dictionary")

        encode_method = params.get("encode_method", "caesar")
        if encode_method not in encode_expert_dict:
            supported = sorted(encode_expert_dict.keys())
            raise ValueError(
                f"Unsupported encode_method '{encode_method}'. Supported: {supported}"
            )

        demonstration_toxicity = params.get("demonstration_toxicity", "toxic")
        if demonstration_toxicity not in {"toxic", "harmless"}:
            raise ValueError(
                "cipherchat_params.demonstration_toxicity must be 'toxic' or 'harmless'"
            )

        language = params.get("language", "en")
        if language not in {"en", "zh"}:
            raise ValueError("cipherchat_params.language must be 'en' or 'zh'")

        instruction_type = params.get(
            "instruction_type", "Crimes_And_Illegal_Activities"
        )
        if instruction_type not in demonstration_dict:
            supported_types = sorted(demonstration_dict.keys())
            raise ValueError(
                f"Unsupported instruction_type '{instruction_type}'. Supported: {supported_types}"
            )

        num_demonstrations = int(params.get("num_demonstrations", 3))
        if num_demonstrations < 0:
            raise ValueError("cipherchat_params.num_demonstrations must be >= 0")

        timeout = int(self.config.get("timeout", 120))
        if timeout <= 0:
            raise ValueError("timeout must be > 0")

        max_tokens = int(self.config.get("max_tokens", 512))
        if max_tokens <= 0:
            raise ValueError("max_tokens must be > 0")

    def _get_pipeline_steps(self) -> List[Dict]:
        return [
            {
                "name": "Generation: Encode Prompt and Execute CipherChat",
                "function": generation.execute,
                "step_type_enum": "GENERATION",
                "config_keys": [
                    "batch_size",
                    "max_tokens",
                    "temperature",
                    "timeout",
                    "cipherchat_params",
                    "_run_id",
                    "_backend",
                    "_client",
                    "_tracker",
                ],
                "input_data_arg_name": "goals",
                "required_args": ["logger", "agent_router", "config"],
            }
        ]

    def run(self, goals: Optional[List[str]] = None, **kwargs) -> List[AttackResult]:
        goals = goals or []
        if not goals:
            return []

        coordinator = self._initialize_coordinator(attack_type="cipherchat")

        # Initialize per-goal tracking BEFORE generation so that
        # generation.py can emit candidate-level traces to the dashboard.
        params = self.config.get("cipherchat_params", {})
        goal_metadata = {
            "attack_type": "cipherchat",
            "encode_method": params.get("encode_method", "caesar"),
            "instruction_type": params.get(
                "instruction_type", "Crimes_And_Illegal_Activities"
            ),
            "language": params.get("language", "en"),
            "demonstration_toxicity": params.get("demonstration_toxicity", "toxic"),
        }
        coordinator.initialize_goals(goals=goals, initial_metadata=goal_metadata)

        if coordinator.goal_tracker:
            self.config["_tracker"] = coordinator.goal_tracker

        pipeline_steps = self._get_pipeline_steps()
        start_step = self.config.get("start_step", 1) - 1

        try:
            results = self._execute_pipeline(
                pipeline_steps, goals, start_step=start_step
            )

            if not results:
                self.logger.warning("Generation produced no output")
                coordinator.finalize_pipeline([], lambda _: False)
                return []

            coordinator.finalize_all_goals(results)
            coordinator.log_summary()
            coordinator.finalize_pipeline(results)
            return rows_to_attack_results(results)

        except Exception:
            coordinator.finalize_on_error("CipherChat pipeline failed with exception")
            raise
