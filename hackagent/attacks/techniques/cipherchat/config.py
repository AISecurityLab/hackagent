# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Configuration for CipherChat attack."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


DEFAULT_CIPHERCHAT_CONFIG: Dict[str, Any] = {
    "attack_type": "cipherchat",
    "cipherchat_params": {
        "encode_method": "caesar",
        "use_system_role": True,
        "use_demonstrations": True,
        "demonstration_toxicity": "toxic",
        "instruction_type": "Crimes_And_Illegal_Activities",
        "language": "en",
        "num_demonstrations": 3,
        "decode_response": True,
    },
    "goals": [],
    "dataset": None,
    "batch_size": 8,
    "max_new_tokens": 512,
    "temperature": 0.0,
    "request_timeout": 120,
    "goal_batch_size": 1,
    "goal_batch_workers": 1,
    "judges": [
        {
            "identifier": "gpt-4-0613",
            "type": "harmbench",
            "agent_type": "OPENAI_SDK",
            "api_key": None,
            "endpoint": None,
        }
    ],
    "batch_size_judge": 1,
    "max_new_tokens_eval": 256,
    "filter_len": 10,
    "judge_request_timeout": 120,
    "judge_temperature": 0.0,
    "max_judge_retries": 1,
    "output_dir": "./logs/runs",
    "run_id": None,
    "start_step": 1,
}


@dataclass
class CipherChatParams:
    encode_method: str = "caesar"
    use_system_role: bool = True
    use_demonstrations: bool = True
    demonstration_toxicity: str = "toxic"
    instruction_type: str = "Crimes_And_Illegal_Activities"
    language: str = "en"
    num_demonstrations: int = 3
    decode_response: bool = True


@dataclass
class CipherChatConfig:
    attack_type: str = "cipherchat"
    cipherchat_params: CipherChatParams = field(default_factory=CipherChatParams)
    goals: List[str] = field(default_factory=list)
    judges: List[Dict[str, Any]] = field(default_factory=list)
    batch_size: int = 8
    max_new_tokens: int = 512
    temperature: float = 0.0
    request_timeout: int = 120
    goal_batch_size: int = 1
    goal_batch_workers: int = 1
    batch_size_judge: int = 1
    max_new_tokens_eval: int = 256
    filter_len: int = 10
    judge_request_timeout: int = 120
    judge_temperature: float = 0.0
    max_judge_retries: int = 1
    dataset: Optional[str] = None
    output_dir: str = "./logs/runs"
    start_step: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "attack_type": self.attack_type,
            "cipherchat_params": vars(self.cipherchat_params),
            "goals": self.goals,
            "judges": self.judges,
            "batch_size": self.batch_size,
            "max_new_tokens": self.max_new_tokens,
            "temperature": self.temperature,
            "request_timeout": self.request_timeout,
            "goal_batch_size": self.goal_batch_size,
            "goal_batch_workers": self.goal_batch_workers,
            "batch_size_judge": self.batch_size_judge,
            "max_new_tokens_eval": self.max_new_tokens_eval,
            "filter_len": self.filter_len,
            "judge_request_timeout": self.judge_request_timeout,
            "judge_temperature": self.judge_temperature,
            "max_judge_retries": self.max_judge_retries,
            "dataset": self.dataset,
            "output_dir": self.output_dir,
            "start_step": self.start_step,
        }
