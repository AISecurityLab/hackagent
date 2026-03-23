# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Configuration for CipherChat attack."""

from typing import Any, Dict

from pydantic import BaseModel, Field

from hackagent.attacks.techniques.config import (
    DEFAULT_CONFIG_BASE,
    ConfigBase,
)


DEFAULT_CIPHERCHAT_CONFIG: Dict[str, Any] = {
    **DEFAULT_CONFIG_BASE,
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
}


class CipherChatParams(BaseModel):
    encode_method: str = "caesar"
    use_system_role: bool = True
    use_demonstrations: bool = True
    demonstration_toxicity: str = "toxic"
    instruction_type: str = "Crimes_And_Illegal_Activities"
    language: str = "en"
    num_demonstrations: int = 3
    decode_response: bool = True


class CipherChatConfig(ConfigBase):
    attack_type: str = "cipherchat"
    cipherchat_params: CipherChatParams = Field(default_factory=CipherChatParams)

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> "CipherChatConfig":
        """Create a :class:`CipherChatConfig` from a plain dictionary."""
        return cls.model_validate(config_dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return self.model_dump()
