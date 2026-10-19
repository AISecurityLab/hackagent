# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Judges, a panel over samples, verdict metrics, and an audit of the panel.

Depth 0: this package imports only :mod:`hackagent.core`.
"""

from hackagent.evaluation.audit import (
    AuditReport,
    JudgeReport,
    RobustnessSpec,
    audit_panel,
)
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
    "AuditReport",
    "EVALUATOR_MAP",
    "HarmBenchJudge",
    "HarmBenchVariantJudge",
    "JailbreakBenchJudge",
    "JudgeReport",
    "KeywordEvaluator",
    "LLMJudge",
    "LengthEvaluator",
    "NuancedJudge",
    "OnTopicJudge",
    "Panel",
    "PatternEvaluator",
    "RagOutcomeJudge",
    "RobustnessSpec",
    "ScorerJudge",
    "audit_panel",
    "fleiss_kappa",
    "majority_vote_rate",
    "mean_score",
    "per_judge_strictness",
    "success_rate",
    "summary",
]
