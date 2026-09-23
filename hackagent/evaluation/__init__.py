# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Judges, a panel over samples, and verdict metrics.

Depth 0: this package imports only :mod:`hackagent.core`.
"""

from hackagent.evaluation.base import AssertionResult
from hackagent.evaluation.judges import (
    EVALUATOR_MAP,
    HarmBenchJudge,
    HarmBenchVariantJudge,
    JailbreakBenchJudge,
    NuancedJudge,
    OnTopicJudge,
    RagOutcomeJudge,
    ScorerJudge,
)
from hackagent.evaluation.metrics import (
    fleiss_kappa,
    majority_vote_rate,
    mean_score,
    per_judge_strictness,
    success_rate,
    summary,
)
from hackagent.evaluation.panel import LLMJudge, Panel
from hackagent.evaluation.patterns import (
    KeywordEvaluator,
    LengthEvaluator,
    PatternEvaluator,
)

__all__ = [
    "AssertionResult",
    "EVALUATOR_MAP",
    "HarmBenchJudge",
    "HarmBenchVariantJudge",
    "JailbreakBenchJudge",
    "KeywordEvaluator",
    "LLMJudge",
    "LengthEvaluator",
    "NuancedJudge",
    "OnTopicJudge",
    "Panel",
    "PatternEvaluator",
    "RagOutcomeJudge",
    "ScorerJudge",
    "fleiss_kappa",
    "majority_vote_rate",
    "mean_score",
    "per_judge_strictness",
    "success_rate",
    "summary",
]
