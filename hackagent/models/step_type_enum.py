# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from enum import Enum


class StepTypeEnum(str, Enum):
    A2A_COMM = "A2A_COMM"
    AGENT_RESPONSE_CHUNK = "AGENT_RESPONSE_CHUNK"
    AGENT_THOUGHT = "AGENT_THOUGHT"
    MCP_STEP = "MCP_STEP"
    OTHER = "OTHER"
    TOOL_CALL = "TOOL_CALL"
    TOOL_RESPONSE = "TOOL_RESPONSE"

    def __str__(self) -> str:
        return str(self.value)
