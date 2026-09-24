# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Chat messages and tool calls."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field

from hackagent.core.contracts._base import FROZEN


class ToolCall(BaseModel):
    """A tool invocation requested by a model."""

    model_config = FROZEN

    id: Optional[str] = None
    name: str
    arguments: str = ""


class Message(BaseModel):
    """One chat message. ``content`` is text or OpenAI-style content parts."""

    model_config = FROZEN

    role: Literal["system", "user", "assistant", "tool"]
    content: Union[str, List[Dict[str, Any]], None] = None
    tool_calls: List[ToolCall] = Field(default_factory=list)
    tool_call_id: Optional[str] = None


__all__ = [
    "Message",
    "ToolCall",
]
