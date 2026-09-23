# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Run-level options that do not belong on :class:`AttackConfig`.

Goal source, batching, output directory, resume step and re-judge live here
so technique configs stay limited to algorithm params and role fields.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field


class RunSpec(BaseModel):
    """Orchestrator-owned run bookkeeping and scheduling knobs."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    goals: List[str] = Field(default_factory=list)
    dataset: Optional[Union[str, Dict[str, Any]]] = None
    intents: Optional[Union[List[Dict[str, Any]], Dict[str, Any]]] = None
    output_dir: str = "./logs/runs"
    run_id: Optional[str] = None
    start_step: int = Field(default=1, ge=1)
    batch_size: int = Field(default=1, ge=1)
    goal_batch_size: int = Field(default=1, ge=1)
    goal_batch_workers: int = Field(default=1, ge=1)
    rejudge: bool = False


__all__ = ["RunSpec"]
