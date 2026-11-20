# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Configuration for repository injection."""

from pathlib import PurePosixPath, PureWindowsPath
from typing import Optional

from pydantic import Field, field_validator

from ...contract import AttackParams, Completion
from .prompts import DEFAULT_INJECTION_TEMPLATE, DEFAULT_TASK


class RepoInjectionParams(AttackParams):
    """Which repository the agent works in, what it is asked, and what is planted.

    ``attacker`` is an optional role: when set, it rewrites the poisoned file
    after each failed attempt, from what the agent did with the last one.
    Without it a single attempt is made per goal (``max_attempts`` then has
    no effect, since nothing changes between tries).
    """

    repo: str = Field(
        description=(
            "Required. Local directory of the repository the agent works in. "
            "Each attempt runs in a fresh copy of it; the original is never "
            "modified. Use a canary copy: the files the agent reads reach the "
            "judges."
        ),
    )
    poison_path: str = Field(
        default="CLAUDE.md",
        description=(
            "Path of the poisoned file, relative to the repository root. It "
            "replaces any file already there, and must stay inside the copy."
        ),
    )
    task: str = Field(
        default=DEFAULT_TASK,
        description=(
            "The benign coding task the agent is given, as the only user message."
        ),
    )
    injection_template: str = Field(
        default=DEFAULT_INJECTION_TEMPLATE,
        description=(
            "Content of the poisoned file. Placeholder: ``{goal}``. The default "
            "reads as ordinary project notes whose 'before running tests' step "
            "carries the goal."
        ),
    )
    max_attempts: int = Field(
        default=3,
        ge=1,
        description="Attempts per goal. Only meaningful with an ``attacker``.",
    )
    keep_workspaces: bool = Field(
        default=False,
        description=(
            "Keep each attempt's copy of the repository instead of deleting it, "
            "and record its path in the attempt's metadata."
        ),
    )
    attacker: Optional[Completion] = Field(
        default=None,
        exclude=True,
        repr=False,
        description=(
            "Optional. Rewrites the poisoned file for each attempt after the "
            "first, from the previous file and what the agent did with it. "
            "Without it, the attack makes a single attempt with the template."
        ),
    )

    @field_validator("poison_path")
    @classmethod
    def _stays_inside(cls, value: str) -> str:
        """Refuse a path that is absolute, climbs out, or names no file."""
        for flavour in (PurePosixPath, PureWindowsPath):
            path = flavour(value)
            if path.is_absolute() or path.anchor or ".." in path.parts:
                raise ValueError(
                    f"poison_path {value!r} must be a relative path inside the "
                    "repository"
                )
        if not PurePosixPath(value.replace("\\", "/")).parts:
            raise ValueError("poison_path must name a file")
        return value


__all__ = ["RepoInjectionParams"]
