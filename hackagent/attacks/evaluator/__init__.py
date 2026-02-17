# Copyright 2025 - AI4I. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Evaluator module for HackAgent attack framework.

This package contains all reusable evaluation components for determining
attack success across different techniques. It centralizes evaluation
logic that was previously scattered across ``shared/`` and individual
technique folders.

Architecture:
    base.py               — BaseJudgeEvaluator ABC + AssertionResult
    judge_evaluators.py   — NuancedEvaluator, JailbreakBenchEvaluator, HarmBenchEvaluator
    pattern_evaluators.py — PatternEvaluator, KeywordEvaluator, LengthEvaluator
    metrics.py            — Success rate, per-goal metrics, summary reports
    sync.py               — Server sync utilities (PATCH Result records)

Usage:
    from hackagent.attacks.evaluator import (
        # LLM-based judge evaluators
        BaseJudgeEvaluator,
        NuancedEvaluator,
        JailbreakBenchEvaluator,
        HarmBenchEvaluator,
        EVALUATOR_MAP,
        AssertionResult,
        # Pattern-based evaluators
        PatternEvaluator,
        KeywordEvaluator,
        LengthEvaluator,
        # Metrics
        calculate_success_rate,
        calculate_per_goal_metrics,
        generate_summary_report,
        # Server sync
        sync_evaluation_to_server,
        update_single_result,
    )
"""

from hackagent.attacks.evaluator.base import AssertionResult, BaseJudgeEvaluator
from hackagent.attacks.evaluator.evaluation_step import BaseEvaluationStep
from hackagent.attacks.evaluator.judge_evaluators import (
    EVALUATOR_MAP,
    HarmBenchEvaluator,
    JailbreakBenchEvaluator,
    NuancedEvaluator,
)
from hackagent.attacks.evaluator.metrics import (
    calculate_confidence_score,
    calculate_per_goal_metrics,
    calculate_success_rate,
    generate_summary_report,
    group_by_goal,
)
from hackagent.attacks.evaluator.pattern_evaluators import (
    KeywordEvaluator,
    LengthEvaluator,
    PatternEvaluator,
)
from hackagent.attacks.evaluator.sync import (
    sync_evaluation_to_server,
    update_single_result,
)

__all__ = [
    # Base
    "AssertionResult",
    "BaseJudgeEvaluator",
    "BaseEvaluationStep",
    # Judge evaluators
    "NuancedEvaluator",
    "JailbreakBenchEvaluator",
    "HarmBenchEvaluator",
    "EVALUATOR_MAP",
    # Pattern evaluators
    "PatternEvaluator",
    "KeywordEvaluator",
    "LengthEvaluator",
    # Metrics
    "calculate_success_rate",
    "calculate_confidence_score",
    "calculate_per_goal_metrics",
    "generate_summary_report",
    "group_by_goal",
    # Sync
    "sync_evaluation_to_server",
    "update_single_result",
]
