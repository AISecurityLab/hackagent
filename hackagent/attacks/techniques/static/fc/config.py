# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Configuration for the image (FC) and text (tFC) flowchart attacks.

Both draw the steps a *step-description generator* writes for the goal
(Zhang et al., FC-Attack, EMNLP 2025 Findings). The generator is the
``attacker`` role. The authors' generator is Mistral-7B-Instruct-v0.1,
LoRA-fine-tuned on benign how-to steps; its weights are not released, so
any model that answers in the same numbered format can stand in.
"""

from typing import ClassVar, Literal, Optional

from pydantic import Field

from ..base import AttackParams, Completion

Layout = Literal["vertical", "horizontal", "tortuous", "s_shaped"]
TextFormat = Literal["dot", "mermaid", "tikz", "plantuml", "ascii"]


class FCParams(AttackParams):
    """How the goal is drawn as a flowchart image."""

    REQUIRED_ROLES: ClassVar[frozenset[str]] = frozenset({"attacker"})

    layout: Layout = Field(
        default="vertical",
        description="Shape of the flowchart: vertical, horizontal, tortuous or s_shaped.",
    )
    dpi: int = Field(
        default=600,
        ge=72,
        le=1200,
        description="Resolution of the rendered flowchart image.",
    )
    num_steps: int = Field(
        default=5,
        ge=1,
        le=10,
        description=(
            "How many of the generated steps the flowchart shows, from the first. "
            "The paper compares 1, 3, 5 and all (at most 10)."
        ),
    )
    truncate_last_step: bool = Field(
        default=False,
        description=(
            "Cut the last step off mid-sentence. Not part of FC-Attack, whose "
            "flowcharts keep every step whole."
        ),
    )
    attacker: Optional[Completion] = Field(
        default=None,
        exclude=True,
        repr=False,
        description=(
            "Step-description generator: writes the numbered steps for the goal "
            "that the flowchart shows."
        ),
    )


class tFCParams(AttackParams):
    """How the goal is written as a textual flowchart."""

    REQUIRED_ROLES: ClassVar[frozenset[str]] = frozenset({"attacker"})

    layout: Layout = Field(
        default="vertical",
        description="Shape of the flowchart: vertical, horizontal, tortuous or s_shaped.",
    )
    text_format: TextFormat = Field(
        default="dot",
        description=(
            "Text language the flowchart is written in: dot, mermaid, tikz, "
            "plantuml or ascii."
        ),
    )
    num_steps: int = Field(
        default=5,
        ge=1,
        le=10,
        description=(
            "How many of the generated steps the flowchart shows, from the first. "
            "The paper compares 1, 3, 5 and all (at most 10)."
        ),
    )
    truncate_last_step: bool = Field(
        default=False,
        description=(
            "Cut the last step off mid-sentence. Not part of FC-Attack, whose "
            "flowcharts keep every step whole."
        ),
    )
    attacker: Optional[Completion] = Field(
        default=None,
        exclude=True,
        repr=False,
        description=(
            "Step-description generator: writes the numbered steps for the goal "
            "that the flowchart shows."
        ),
    )
