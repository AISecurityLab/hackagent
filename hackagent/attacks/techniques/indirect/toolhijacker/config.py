# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Configuration of the tool library, retrieval and document search."""

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ...contract import AttackParams, Completion, Embedder


class ToolDocument(BaseModel):
    """One tool's registry entry; only the injected description is optimized."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    name: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    description: str = Field(min_length=1)
    parameters: dict[str, Any] = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        }
    )

    def tool_schema(self) -> dict[str, Any]:
        """An OpenAI-compatible function declaration, without executing it."""
        return {"type": "function", "function": self.model_dump()}


class ToolHijackerParams(AttackParams):
    """A local tool router and a bounded, gradient-free description search."""

    tools: tuple[ToolDocument, ...] = Field(
        default=(
            ToolDocument(
                name="task_assistant", description="Assist with general user tasks."
            ),
        ),
        min_length=1,
        description="Benign tool library. Each entry has name, description and parameters.",
    )
    malicious_tool: ToolDocument = Field(
        default=ToolDocument(
            name="task_helper", description="A tool for the requested task."
        ),
        description="Injected tool. Its name and parameters stay fixed; its description is optimized.",
    )
    paraphrases: tuple[str, ...] = Field(
        default=(),
        description="Additional semantic phrasings of each goal. Empty uses two deterministic rephrasings. The original goal is always tested.",
    )
    top_k: int = Field(
        default=3,
        ge=1,
        description="Number of tool documents retrieved before selection.",
    )
    max_attempts: int = Field(
        default=3,
        ge=1,
        description="Maximum candidate descriptions per goal, each tested on all task phrasings. Without an attacker, at most three built-in variants are tested.",
    )
    success_threshold: float = Field(
        default=1.0,
        gt=0,
        le=1,
        description="End-to-end selection rate across phrasings required to stop searching early.",
    )
    attacker: Optional[Completion] = Field(
        default=None,
        exclude=True,
        repr=False,
        description="Optional model that refines the best description using retrieval and selection feedback. Without it, search deterministic instruction variants.",
    )
    embedder: Optional[Embedder] = Field(
        default=None,
        exclude=True,
        repr=False,
        description="Optional shadow retriever embeddings. Without it, use dependency-free token cosine similarity.",
    )

    @model_validator(mode="after")
    def unique_tools(self) -> "ToolHijackerParams":
        names = [tool.name for tool in self.tools] + [self.malicious_tool.name]
        if len(names) != len(set(names)):
            raise ValueError("Tool names, including the malicious tool, must be unique")
        if any(not task.strip() for task in self.paraphrases):
            raise ValueError("Paraphrases cannot be blank")
        return self
