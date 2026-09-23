# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Scripted :class:`~hackagent.attacks.ports.Judge` for attack-seam tests."""

from __future__ import annotations

from typing import List, Optional

from hackagent.core.contracts import Sample, Verdict


class FakeJudge:
    """Returns scripted scores/verdicts and records every sample seen."""

    def __init__(
        self,
        *,
        score: float = 0.0,
        success: bool = False,
        scores: Optional[List[float]] = None,
    ) -> None:
        self._default_score = score
        self._success = success
        self._scores = list(scores) if scores is not None else None
        self.samples: List[Sample] = []

    def _next_score(self) -> float:
        if self._scores is not None:
            if not self._scores:
                raise AssertionError("FakeJudge score script exhausted")
            return float(self._scores.pop(0))
        return float(self._default_score)

    def score(self, sample: Sample) -> float:
        self.samples.append(sample)
        return self._next_score()

    def evaluate(self, sample: Sample) -> Verdict:
        value = self.score(sample)
        success = self._success if self._scores is None else value >= 5.0
        if self._scores is None and not self._success:
            success = value >= 5.0
        return Verdict(success=success, score=value)
