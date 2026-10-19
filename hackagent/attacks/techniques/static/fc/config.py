# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Configuration for the image (FC) and text (tFC) flowchart attacks."""

from typing import Literal

from pydantic import Field

from ..base import AttackParams

Layout = Literal["vertical", "horizontal", "tortuous", "s_shaped"]
TextFormat = Literal["dot", "mermaid", "tikz", "plantuml", "ascii"]


class FCParams(AttackParams):
    """How the goal is drawn as a flowchart image."""

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
        default=6, ge=2, le=15, description="How many steps the goal is split into."
    )
    truncate_last_step: bool = Field(
        default=True,
        description=(
            "Cut the last step off mid-sentence, so the target is invited to "
            "complete it."
        ),
    )


class tFCParams(AttackParams):
    """How the goal is written as a textual flowchart."""

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
        default=6, ge=2, le=15, description="How many steps the goal is split into."
    )
    truncate_last_step: bool = Field(
        default=True,
        description=(
            "Cut the last step off mid-sentence, so the target is invited to "
            "complete it."
        ),
    )
