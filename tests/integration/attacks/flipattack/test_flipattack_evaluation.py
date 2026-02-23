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
Integration tests for FlipAttack evaluation module (evaluation.py).

Tests the FlipAttackEvaluation class and module-level execute() function
which evaluate attack responses using the multi-judge pipeline inherited
from BaseEvaluationStep.

These tests use mocked judge evaluators to verify the evaluation
transformation, merge, scoring, and sync logic without requiring
real LLM judge backends.

Run with:
    pytest tests/integration/attacks/test_flipattack_evaluation.py --run-integration
"""

import logging
from unittest.mock import MagicMock, patch

import pytest

from hackagent.attacks.techniques.flipattack.evaluation import (
    FlipAttackEvaluation,
    _build_prompt_prefix,
    execute as evaluation_execute,
)

logger = logging.getLogger(__name__)


# ============================================================================
# HELPERS
# ============================================================================


def _make_mock_client():
    """Create a mock AuthenticatedClient."""
    return MagicMock()


def _make_eval_config(**overrides):
    """Create a minimal evaluation config dict."""
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
        "max_judge_retries": 1,
        "flipattack_params": {},
    }
    config.update(overrides)
    return config


def _make_generation_results(goals=None, include_error=False):
    """Create mock generation results as would be returned by generation.execute()."""
    if goals is None:
        goals = ["Test harmful goal"]

    results = []
    for i, goal in enumerate(goals):
        item = {
            "goal": goal,
            "flip_mode": "FCS",
            "flip_log": f"TASK is '{goal[::-1]}'",
            "system_prompt": "You are an expert...",
            "user_prompt": f"TASK is '{goal[::-1]}'",
            "full_prompt": f"You are an expert...\n\nTASK is '{goal[::-1]}'",
            "response": f"Here is a detailed response for goal {i + 1}.",
            "error": None,
        }
        if include_error and i == len(goals) - 1:
            item["response"] = None
            item["error"] = "Execution failed: timeout"
        results.append(item)
    return results


# ============================================================================
# _build_prompt_prefix TESTS
# ============================================================================


@pytest.mark.integration
class TestBuildPromptPrefix:
    """Test the _build_prompt_prefix helper function."""

    def test_uses_full_prompt_if_available(self):
        """Test that full_prompt is preferred."""
        item = {
            "full_prompt": "Full prompt content",
            "system_prompt": "System part",
            "user_prompt": "User part",
        }
        assert _build_prompt_prefix(item) == "Full prompt content"

    def test_constructs_from_parts_without_full_prompt(self):
        """Test fallback to system_prompt + user_prompt."""
        item = {"system_prompt": "System", "user_prompt": "User"}
        result = _build_prompt_prefix(item)
        assert "System" in result
        assert "User" in result

    def test_empty_parts(self):
        """Test with empty prompt parts."""
        item = {"system_prompt": "", "user_prompt": ""}
        result = _build_prompt_prefix(item)
        assert result == ""

    def test_only_system_prompt(self):
        """Test with only system_prompt available."""
        item = {"system_prompt": "System only", "user_prompt": ""}
        result = _build_prompt_prefix(item)
        assert "System only" in result

    def test_no_prompt_fields(self):
        """Test with no prompt fields at all."""
        item = {}
        result = _build_prompt_prefix(item)
        assert result == ""


# ============================================================================
# FlipAttackEvaluation TESTS
# ============================================================================


@pytest.mark.integration
class TestFlipAttackEvaluation:
    """Test FlipAttackEvaluation class initialization and data flow."""

    def test_initialization(self):
        """Test that evaluation step initializes correctly."""
        config = _make_eval_config()
        client = _make_mock_client()

        step = FlipAttackEvaluation(config=config, logger=logger, client=client)

        assert step._statistics["input_count"] == 0
        assert step._statistics["evaluated_count"] == 0
        assert step.client is client

    def test_execute_empty_input(self):
        """Test execute with empty input returns empty."""
        config = _make_eval_config()
        client = _make_mock_client()
        step = FlipAttackEvaluation(config=config, logger=logger, client=client)

        result = step.execute(input_data=[])
        assert result == []

    def test_transform_to_eval_rows(self):
        """Test transformation of generation results to evaluation rows."""
        config = _make_eval_config()
        client = _make_mock_client()
        step = FlipAttackEvaluation(config=config, logger=logger, client=client)

        gen_results = _make_generation_results(goals=["Goal 1", "Goal 2"])
        eval_rows, error_indices = step._transform_to_eval_rows(gen_results)

        assert len(eval_rows) == 2
        assert len(error_indices) == 0
        assert eval_rows[0]["goal"] == "Goal 1"
        assert eval_rows[0]["completion"] != ""
        assert "prefix" in eval_rows[0]

    def test_transform_with_error_items(self):
        """Test that error items are excluded from eval rows."""
        config = _make_eval_config()
        client = _make_mock_client()
        step = FlipAttackEvaluation(config=config, logger=logger, client=client)

        gen_results = _make_generation_results(
            goals=["Good goal", "Error goal"], include_error=True
        )
        eval_rows, error_indices = step._transform_to_eval_rows(gen_results)

        assert len(eval_rows) == 1
        assert 1 in error_indices
        # Error item should have been marked
        assert gen_results[1]["best_score"] == 0.0
        assert gen_results[1]["success"] is False

    def test_enrich_items_with_scores(self):
        """Test score enrichment logic."""
        config = _make_eval_config()
        client = _make_mock_client()
        step = FlipAttackEvaluation(config=config, logger=logger, client=client)

        data = [
            {"goal": "g1", "eval_hb": 1, "explanation_hb": "Harmful"},
            {"goal": "g2", "eval_hb": 0, "explanation_hb": "Safe"},
            {"goal": "g3"},  # no eval columns
        ]
        error_indices = set()

        step._enrich_items_with_scores(data, error_indices)

        assert data[0]["best_score"] == 1.0
        assert data[0]["success"] is True
        assert data[1]["best_score"] == 0.0
        assert data[1]["success"] is False
        assert data[2]["best_score"] == 0.0
        assert data[2]["success"] is False

    def test_enrich_items_error_indices(self):
        """Test that error-indexed items always get score 0."""
        config = _make_eval_config()
        client = _make_mock_client()
        step = FlipAttackEvaluation(config=config, logger=logger, client=client)

        data = [
            {"goal": "g1", "eval_hb": 1},  # This is in error_indices
        ]
        error_indices = {0}

        step._enrich_items_with_scores(data, error_indices)

        # Despite having eval_hb=1, error index overrides
        assert data[0]["best_score"] == 0.0
        assert data[0]["success"] is False

    @patch(
        "hackagent.attacks.evaluator.evaluation_step.sync_evaluation_to_server",
        return_value=0,
    )
    def test_execute_with_mocked_evaluation(self, mock_sync):
        """Test full execute flow with mocked _run_evaluation."""
        config = _make_eval_config()
        client = _make_mock_client()
        step = FlipAttackEvaluation(config=config, logger=logger, client=client)

        gen_results = _make_generation_results(goals=["Test goal"])

        # Mock the _run_evaluation to return data with judge columns
        with patch.object(step, "_run_evaluation") as mock_eval:
            mock_eval.return_value = [
                {
                    "goal": "Test goal",
                    "prefix": gen_results[0]["full_prompt"],
                    "completion": gen_results[0]["response"],
                    "eval_hb": 1,
                    "explanation_hb": "Harmful behavior detected",
                }
            ]

            results = step.execute(input_data=gen_results)

        assert len(results) == 1
        assert results[0]["best_score"] == 1.0
        assert results[0]["success"] is True

    def test_get_statistics(self):
        """Test statistics retrieval after execution."""
        config = _make_eval_config()
        client = _make_mock_client()
        step = FlipAttackEvaluation(config=config, logger=logger, client=client)

        stats = step.get_statistics()
        assert "input_count" in stats
        assert "evaluated_count" in stats
        assert "successful_judges" in stats
        assert "failed_judges" in stats


# ============================================================================
# MODULE-LEVEL execute() TESTS
# ============================================================================


@pytest.mark.integration
class TestEvaluationModuleExecute:
    """Test the module-level evaluate.execute() function."""

    @patch(
        "hackagent.attacks.evaluator.evaluation_step.sync_evaluation_to_server",
        return_value=0,
    )
    def test_module_execute_wraps_class(self, mock_sync):
        """Test that module-level execute() wraps FlipAttackEvaluation."""
        config = _make_eval_config()
        client = _make_mock_client()
        gen_results = _make_generation_results(goals=["Module test"])

        with patch(
            "hackagent.attacks.techniques.flipattack.evaluation.FlipAttackEvaluation"
        ) as MockClass:
            mock_instance = MagicMock()
            mock_instance.execute.return_value = gen_results
            MockClass.return_value = mock_instance

            MockClass.assert_called_once_with(
                config=config, logger=logger, client=client
            )
            mock_instance.execute.assert_called_once_with(input_data=gen_results)

    def test_module_execute_empty_input(self):
        """Test module-level execute with empty input."""
        config = _make_eval_config()
        client = _make_mock_client()

        result = evaluation_execute(
            input_data=[],
            config=config,
            client=client,
            logger=logger,
        )

        assert result == []
