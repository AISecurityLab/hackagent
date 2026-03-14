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
Integration tests for AdvPrefix evaluation pipeline (advprefix/evaluation.py).

Tests the EvaluationPipeline class which extends BaseEvaluationStep with
AdvPrefix-specific aggregation and selection stages.

These tests verify:
- Pipeline initialization and config parsing
- Full execute() flow with mocked judges
- Aggregation of evaluation results by goal/prefix
- Selection of optimal prefixes (PASR, NLL, sub-prefix filtering)
- NLL filtering
- Statistics tracking

Run with:
    pytest tests/integration/attacks/test_advprefix_evaluation.py --run-integration
"""

import logging
from unittest.mock import MagicMock, patch

import pytest

from hackagent.attacks.techniques.advprefix.evaluation import (
    EvaluationPipeline,
    GROUP_KEYS,
)
from hackagent.attacks.techniques.advprefix.config import EvaluationPipelineConfig

logger = logging.getLogger(__name__)


# ============================================================================
# HELPERS
# ============================================================================


def _make_mock_client():
    """Create a mock AuthenticatedClient."""
    return MagicMock()


def _make_pipeline_config(**overrides):
    """Create a minimal evaluation pipeline config dict."""
    config = {
        "judges": [
            {
                "identifier": "gpt-4-0613",
                "type": "harmbench",
                "agent_type": "OPENAI_SDK",
            }
        ],
        "batch_size_judge": 1,
        "max_new_tokens_eval": 256,
        "filter_len": 10,
        "judge_request_timeout": 120,
        "judge_temperature": 0.0,
        "max_ce": None,
        "n_prefixes_per_goal": 2,
        "nll_tol": 999,
        "pasr_tol": 0,
    }
    config.update(overrides)
    return config


def _make_completion_data(n_goals=2, n_prefixes=2, n_completions=2):
    """Create mock completion data as would come from Execution stage."""
    data = []
    for g in range(n_goals):
        for p in range(n_prefixes):
            for c in range(n_completions):
                data.append(
                    {
                        "goal": f"Goal {g}",
                        "prefix": f"Prefix {g}-{p}",
                        "completion": f"Completion {g}-{p}-{c}",
                        "prefix_nll": 0.5 + p * 0.1,
                        "model_name": "test-model",
                        "meta_prefix": "Write a story:",
                        "temperature": 0.7,
                        "result_id": f"result-{g}",
                    }
                )
    return data


# ============================================================================
# INITIALIZATION TESTS
# ============================================================================


@pytest.mark.integration
class TestEvaluationPipelineInit:
    """Test EvaluationPipeline initialization."""

    def test_initialization_from_dict(self):
        """Test initialization with dict config."""
        config = _make_pipeline_config()
        client = _make_mock_client()

        pipeline = EvaluationPipeline(config=config, logger=logger, client=client)

        assert isinstance(pipeline.config, EvaluationPipelineConfig)
        assert len(pipeline.config.judges) == 1
        assert pipeline._statistics["aggregated_count"] == 0
        assert pipeline._statistics["selected_count"] == 0

    def test_initialization_preserves_judge_config(self):
        """Test that judge configs are preserved in parsed config."""
        config = _make_pipeline_config(
            judges=[
                {"identifier": "j1", "type": "harmbench"},
                {"identifier": "j2", "type": "jailbreakbench"},
            ]
        )
        client = _make_mock_client()

        pipeline = EvaluationPipeline(config=config, logger=logger, client=client)

        assert len(pipeline.config.judges) == 2

    def test_initialization_with_selection_params(self):
        """Test initialization with custom selection parameters."""
        config = _make_pipeline_config(
            n_prefixes_per_goal=5,
            nll_tol=0.5,
            pasr_tol=0.1,
        )
        client = _make_mock_client()

        pipeline = EvaluationPipeline(config=config, logger=logger, client=client)

        assert pipeline.config.n_prefixes_per_goal == 5
        assert pipeline.config.nll_tol == 0.5
        assert pipeline.config.pasr_tol == 0.1


# ============================================================================
# GROUP_KEYS TESTS
# ============================================================================


@pytest.mark.integration
class TestGroupKeys:
    """Test GROUP_KEYS constant."""

    def test_group_keys_defined(self):
        """Test that GROUP_KEYS contains goal and prefix."""
        assert GROUP_KEYS == ["goal", "prefix"]


# ============================================================================
# EXECUTE PIPELINE TESTS
# ============================================================================


@pytest.mark.integration
class TestEvaluationPipelineExecute:
    """Test the full execute() pipeline flow."""

    def test_execute_empty_input(self):
        """Test execute with empty input returns empty list."""
        config = _make_pipeline_config()
        pipeline = EvaluationPipeline(
            config=config, logger=logger, client=_make_mock_client()
        )

        result = pipeline.execute(input_data=[])
        assert result == []

    @patch(
        "hackagent.attacks.evaluator.evaluation_step.sync_evaluation_to_server",
        return_value=0,
    )
    def test_execute_flow_with_mocked_evaluation(self, mock_sync):
        """Test full pipeline with mocked _run_evaluation."""
        config = _make_pipeline_config()
        pipeline = EvaluationPipeline(
            config=config, logger=logger, client=_make_mock_client()
        )

        input_data = _make_completion_data(n_goals=1, n_prefixes=2, n_completions=1)

        with patch.object(pipeline, "_run_evaluation") as mock_eval:
            # Mock evaluation returns data with harmbench scores
            mock_eval.return_value = [
                {**row, "eval_hb": 1 if i == 0 else 0, "explanation_hb": "test"}
                for i, row in enumerate(input_data)
            ]

            results = pipeline.execute(input_data=input_data)

        assert isinstance(results, list)
        assert pipeline._statistics["input_count"] == len(input_data)

    @patch(
        "hackagent.attacks.evaluator.evaluation_step.sync_evaluation_to_server",
        return_value=0,
    )
    def test_execute_tracks_statistics(self, mock_sync):
        """Test that execute updates statistics at each stage."""
        config = _make_pipeline_config()
        pipeline = EvaluationPipeline(
            config=config, logger=logger, client=_make_mock_client()
        )

        input_data = _make_completion_data(n_goals=1, n_prefixes=1, n_completions=1)

        with patch.object(pipeline, "_run_evaluation") as mock_eval:
            mock_eval.return_value = [
                {**row, "eval_hb": 1, "explanation_hb": "test"} for row in input_data
            ]

            pipeline.execute(input_data=input_data)

        stats = pipeline._statistics
        assert stats["input_count"] > 0
        assert stats["evaluated_count"] > 0


# ============================================================================
# AGGREGATION TESTS
# ============================================================================


@pytest.mark.integration
class TestEvaluationPipelineAggregation:
    """Test the aggregation stage."""

    def test_aggregation_groups_by_goal_prefix(self):
        """Test that results are grouped by goal and prefix."""
        config = _make_pipeline_config()
        pipeline = EvaluationPipeline(
            config=config, logger=logger, client=_make_mock_client()
        )

        # Create data with multiple completions per goal/prefix
        input_data = [
            {
                "goal": "g1",
                "prefix": "p1",
                "eval_hb": 1,
                "prefix_nll": 0.5,
                "model_name": "m",
            },
            {
                "goal": "g1",
                "prefix": "p1",
                "eval_hb": 0,
                "prefix_nll": 0.5,
                "model_name": "m",
            },
            {
                "goal": "g1",
                "prefix": "p2",
                "eval_hb": 1,
                "prefix_nll": 0.3,
                "model_name": "m",
            },
        ]

        aggregated = pipeline._run_aggregation(input_data)

        # Should have 2 groups: (g1, p1) and (g1, p2)
        assert len(aggregated) == 2

        # Find g1/p1 group
        g1_p1 = next(r for r in aggregated if r["prefix"] == "p1")
        assert g1_p1["n_eval_samples"] == 2
        assert g1_p1["eval_hb_mean"] == 0.5  # (1+0)/2

    def test_aggregation_preserves_metadata(self):
        """Test that aggregation preserves first-row metadata."""
        config = _make_pipeline_config()
        pipeline = EvaluationPipeline(
            config=config, logger=logger, client=_make_mock_client()
        )

        input_data = [
            {
                "goal": "g1",
                "prefix": "p1",
                "eval_hb": 1,
                "prefix_nll": 0.5,
                "model_name": "test-model",
                "meta_prefix": "Write:",
                "temperature": 0.8,
                "result_id": "rid-1",
            },
        ]

        aggregated = pipeline._run_aggregation(input_data)

        assert len(aggregated) == 1
        assert aggregated[0]["model_name"] == "test-model"
        assert aggregated[0]["meta_prefix"] == "Write:"
        assert aggregated[0]["result_id"] == "rid-1"


# ============================================================================
# NLL FILTERING TESTS
# ============================================================================


@pytest.mark.integration
class TestNllFiltering:
    """Test NLL (cross-entropy) filtering."""

    def test_filter_by_nll(self):
        """Test filtering by NLL threshold."""
        config = _make_pipeline_config()
        pipeline = EvaluationPipeline(
            config=config, logger=logger, client=_make_mock_client()
        )

        data = [
            {"prefix_nll": 0.3},
            {"prefix_nll": 0.5},
            {"prefix_nll": 0.9},
            {"prefix_nll": 1.5},
        ]

        filtered = pipeline._filter_by_nll(data, max_ce_threshold=0.8)

        assert len(filtered) == 2
        assert all(item["prefix_nll"] < 0.8 for item in filtered)

    def test_filter_no_nll_key(self):
        """Test filtering when prefix_nll key is missing."""
        config = _make_pipeline_config()
        pipeline = EvaluationPipeline(
            config=config, logger=logger, client=_make_mock_client()
        )

        data = [{"goal": "g1"}, {"goal": "g2"}]

        filtered = pipeline._filter_by_nll(data, max_ce_threshold=0.8)

        # Should return original data unchanged
        assert len(filtered) == 2

    def test_filter_all_pass(self):
        """Test when all items pass the threshold."""
        config = _make_pipeline_config()
        pipeline = EvaluationPipeline(
            config=config, logger=logger, client=_make_mock_client()
        )

        data = [{"prefix_nll": 0.1}, {"prefix_nll": 0.2}]

        filtered = pipeline._filter_by_nll(data, max_ce_threshold=1.0)
        assert len(filtered) == 2

    def test_filter_none_pass(self):
        """Test when no items pass the threshold."""
        config = _make_pipeline_config()
        pipeline = EvaluationPipeline(
            config=config, logger=logger, client=_make_mock_client()
        )

        data = [{"prefix_nll": 0.9}, {"prefix_nll": 1.5}]

        filtered = pipeline._filter_by_nll(data, max_ce_threshold=0.1)
        assert len(filtered) == 0


# ============================================================================
# SELECTION TESTS
# ============================================================================


@pytest.mark.integration
class TestEvaluationPipelineSelection:
    """Test the prefix selection stage."""

    def test_select_prefixes_for_goal_highest_pasr(self):
        """Test that prefix with highest PASR is selected first."""
        config = _make_pipeline_config(n_prefixes_per_goal=1)
        pipeline = EvaluationPipeline(
            config=config, logger=logger, client=_make_mock_client()
        )

        group = [
            {"goal": "g1", "prefix": "p1", "pasr": 0.8, "prefix_nll": 0.5},
            {"goal": "g1", "prefix": "p2", "pasr": 0.9, "prefix_nll": 0.6},
            {"goal": "g1", "prefix": "p3", "pasr": 0.7, "prefix_nll": 0.4},
        ]

        selected = pipeline._select_prefixes_for_goal(group)

        assert len(selected) == 1
        assert selected[0]["prefix"] == "p2"  # Highest PASR

    def test_select_multiple_prefixes(self):
        """Test selection of multiple prefixes per goal."""
        config = _make_pipeline_config(n_prefixes_per_goal=2, pasr_tol=0.5, nll_tol=999)
        pipeline = EvaluationPipeline(
            config=config, logger=logger, client=_make_mock_client()
        )

        group = [
            {"goal": "g1", "prefix": "p1", "pasr": 0.9, "prefix_nll": 0.5},
            {"goal": "g1", "prefix": "p2", "pasr": 0.8, "prefix_nll": 0.3},
            {"goal": "g1", "prefix": "p3", "pasr": 0.7, "prefix_nll": 0.4},
        ]

        selected = pipeline._select_prefixes_for_goal(group)

        assert len(selected) == 2
        # First should be highest PASR
        assert selected[0]["prefix"] == "p1"

    def test_sub_prefix_elimination(self):
        """Test that sub-prefixes are eliminated."""
        config = _make_pipeline_config(n_prefixes_per_goal=3, pasr_tol=1.0, nll_tol=999)
        pipeline = EvaluationPipeline(
            config=config, logger=logger, client=_make_mock_client()
        )

        group = [
            {"goal": "g1", "prefix": "Write a", "pasr": 0.9, "prefix_nll": 0.5},
            {"goal": "g1", "prefix": "Write a story", "pasr": 0.8, "prefix_nll": 0.3},
            {"goal": "g1", "prefix": "Create", "pasr": 0.7, "prefix_nll": 0.4},
        ]

        selected = pipeline._select_prefixes_for_goal(group)

        # "Write a story" starts with "Write a", so it should be eliminated
        prefixes = [s["prefix"] for s in selected]
        assert "Write a" in prefixes
        assert "Write a story" not in prefixes


# ============================================================================
# PIPELINE STATISTICS TESTS
# ============================================================================


@pytest.mark.integration
class TestEvaluationPipelineStatistics:
    """Test pipeline statistics tracking."""

    def test_extended_statistics(self):
        """Test that pipeline has extended statistics fields."""
        config = _make_pipeline_config()
        pipeline = EvaluationPipeline(
            config=config, logger=logger, client=_make_mock_client()
        )

        stats = pipeline._statistics
        assert "aggregated_count" in stats
        assert "selected_count" in stats
        assert stats["aggregated_count"] == 0
        assert stats["selected_count"] == 0

    def test_log_pipeline_statistics_no_error(self):
        """Test that logging statistics doesn't error."""
        config = _make_pipeline_config()
        pipeline = EvaluationPipeline(
            config=config, logger=logger, client=_make_mock_client()
        )

        pipeline._statistics["input_count"] = 10
        pipeline._statistics["evaluated_count"] = 10
        pipeline._statistics["aggregated_count"] = 5
        pipeline._statistics["selected_count"] = 2
        pipeline._statistics["successful_judges"] = ["harmbench"]

        # Should not raise
        pipeline._log_pipeline_statistics()
