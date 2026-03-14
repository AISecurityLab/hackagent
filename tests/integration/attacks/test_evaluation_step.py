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
Integration tests for BaseEvaluationStep (evaluation_step.py).

Tests the shared foundation for all evaluation pipeline stages, covering:
- Multi-judge evaluation orchestration
- Judge type inference from model identifiers
- Agent type resolution (string/enum → AgentTypeEnum)
- EvaluatorConfig construction from raw judge config dicts
- Result merging via (goal, prefix, completion) lookup keys
- Best-score computation across judge columns
- Judge configuration preparation and validation

Run with:
    pytest tests/integration/attacks/test_evaluation_step.py --run-integration
"""

import logging
from unittest.mock import MagicMock

import pytest

from hackagent.attacks.evaluator.evaluation_step import (
    BaseEvaluationStep,
    JUDGE_AGG_COLUMN_MAP,
    JUDGE_COLUMN_MAP,
    JUDGE_MEAN_COLUMN_MAP,
    JUDGE_TYPE_LABELS,
    MERGE_KEYS,
)
from hackagent.router.types import AgentTypeEnum

logger = logging.getLogger(__name__)


# ============================================================================
# HELPERS
# ============================================================================


def _make_mock_client():
    """Create a mock AuthenticatedClient."""
    return MagicMock()


def _make_step(config=None, **overrides):
    """Create a BaseEvaluationStep with default config."""
    cfg = config or {
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
    }
    cfg.update(overrides)
    return BaseEvaluationStep(config=cfg, logger=logger, client=_make_mock_client())


# ============================================================================
# CONSTANTS TESTS
# ============================================================================


@pytest.mark.integration
class TestEvaluationStepConstants:
    """Test that module-level constants are properly defined."""

    def test_merge_keys(self):
        """Test MERGE_KEYS contains expected keys."""
        assert MERGE_KEYS == ["goal", "prefix", "completion"]

    def test_judge_type_labels(self):
        """Test JUDGE_TYPE_LABELS maps expected types."""
        assert "jailbreakbench" in JUDGE_TYPE_LABELS
        assert "harmbench" in JUDGE_TYPE_LABELS
        assert "nuanced" in JUDGE_TYPE_LABELS

    def test_judge_column_map(self):
        """Test JUDGE_COLUMN_MAP has paired columns (eval, explanation)."""
        for judge_type, cols in JUDGE_COLUMN_MAP.items():
            assert len(cols) == 2, f"Expected 2 columns for {judge_type}"
            assert cols[0].startswith("eval_")
            assert cols[1].startswith("explanation_")

    def test_judge_agg_column_map(self):
        """Test JUDGE_AGG_COLUMN_MAP has eval columns."""
        for judge_type, col in JUDGE_AGG_COLUMN_MAP.items():
            assert col.startswith("eval_"), f"Expected eval_ prefix for {judge_type}"

    def test_judge_mean_column_map(self):
        """Test JUDGE_MEAN_COLUMN_MAP has mean columns."""
        for judge_type, col in JUDGE_MEAN_COLUMN_MAP.items():
            assert "_mean" in col, f"Expected _mean suffix for {judge_type}"

    def test_class_attributes_match_constants(self):
        """Test that class attributes match module-level constants."""
        step = _make_step()
        assert step.MERGE_KEYS is MERGE_KEYS
        assert step.JUDGE_TYPE_LABELS is JUDGE_TYPE_LABELS
        assert step.JUDGE_COLUMN_MAP is JUDGE_COLUMN_MAP


# ============================================================================
# infer_judge_type TESTS
# ============================================================================


@pytest.mark.integration
class TestInferJudgeType:
    """Test judge type inference from model identifiers."""

    def test_harmbench_inference(self):
        """Test inferring harmbench from identifier."""
        assert BaseEvaluationStep.infer_judge_type("gpt-4-harmbench") == "harmbench"
        assert BaseEvaluationStep.infer_judge_type("HarmBench-eval") == "harmbench"

    def test_nuanced_inference(self):
        """Test inferring nuanced from identifier."""
        assert BaseEvaluationStep.infer_judge_type("nuanced-judge") == "nuanced"
        assert BaseEvaluationStep.infer_judge_type("my-Nuanced-model") == "nuanced"

    def test_jailbreakbench_inference(self):
        """Test inferring jailbreakbench from identifier."""
        assert (
            BaseEvaluationStep.infer_judge_type("jailbreak-detector")
            == "jailbreakbench"
        )
        assert (
            BaseEvaluationStep.infer_judge_type("Jailbreak-bench") == "jailbreakbench"
        )

    def test_unknown_identifier_returns_default(self):
        """Test fallback to default when identifier doesn't match."""
        assert BaseEvaluationStep.infer_judge_type("gpt-4-0613") is None
        assert (
            BaseEvaluationStep.infer_judge_type("gpt-4-0613", "harmbench")
            == "harmbench"
        )

    def test_none_identifier_returns_default(self):
        """Test None identifier returns default."""
        assert BaseEvaluationStep.infer_judge_type(None) is None
        assert BaseEvaluationStep.infer_judge_type(None, "nuanced") == "nuanced"

    def test_empty_identifier_returns_default(self):
        """Test empty string identifier returns default."""
        assert BaseEvaluationStep.infer_judge_type("") is None
        assert BaseEvaluationStep.infer_judge_type("", "harmbench") == "harmbench"


# ============================================================================
# resolve_agent_type TESTS
# ============================================================================


@pytest.mark.integration
class TestResolveAgentType:
    """Test agent type resolution."""

    def test_enum_passthrough(self):
        """Test that AgentTypeEnum passes through unchanged."""
        step = _make_step()
        assert (
            step.resolve_agent_type(AgentTypeEnum.OPENAI_SDK)
            == AgentTypeEnum.OPENAI_SDK
        )
        assert step.resolve_agent_type(AgentTypeEnum.OLLAMA) == AgentTypeEnum.OLLAMA

    def test_string_resolution(self):
        """Test string-to-enum resolution."""
        step = _make_step()
        assert step.resolve_agent_type("OPENAI_SDK") == AgentTypeEnum.OPENAI_SDK
        assert step.resolve_agent_type("OLLAMA") == AgentTypeEnum.OLLAMA
        assert step.resolve_agent_type("LITELLM") == AgentTypeEnum.LITELLM

    def test_none_defaults_to_openai_sdk(self):
        """Test that None defaults to OPENAI_SDK."""
        step = _make_step()
        assert step.resolve_agent_type(None) == AgentTypeEnum.OPENAI_SDK

    def test_empty_string_defaults_to_openai_sdk(self):
        """Test that empty string defaults to OPENAI_SDK."""
        step = _make_step()
        assert step.resolve_agent_type("") == AgentTypeEnum.OPENAI_SDK

    def test_invalid_string_defaults_with_warning(self):
        """Test that invalid string falls back with warning."""
        step = _make_step()
        result = step.resolve_agent_type("NONEXISTENT_TYPE")
        assert result == AgentTypeEnum.OPENAI_SDK


# ============================================================================
# _build_base_eval_config TESTS
# ============================================================================


@pytest.mark.integration
class TestBuildBaseEvalConfig:
    """Test evaluator base config construction."""

    def test_extracts_from_raw_config(self):
        """Test extraction from top-level config keys."""
        step = _make_step()
        config = step._build_base_eval_config()

        assert config["batch_size"] == 1
        assert config["max_new_tokens_eval"] == 256
        assert config["filter_len"] == 10
        assert config["request_timeout"] == 120
        assert config["temperature"] == 0.0
        assert config["max_judge_retries"] == 1

    def test_technique_params_fallback(self):
        """Test fallback to technique_params when top-level keys missing."""
        step = _make_step(
            config={
                "judges": [{"identifier": "test", "type": "harmbench"}],
                # No top-level batch_size_judge etc.
            }
        )
        technique_params = {
            "judge_batch_size": 8,
            "judge_max_new_tokens_eval": 512,
            "judge_filter_len": 20,
            "judge_request_timeout": 60,
            "judge_temperature": 0.5,
            "judge_max_retries": 3,
        }
        config = step._build_base_eval_config(technique_params=technique_params)

        assert config["batch_size"] == 8
        assert config["max_new_tokens_eval"] == 512
        assert config["filter_len"] == 20
        assert config["request_timeout"] == 60
        assert config["temperature"] == 0.5
        assert config["max_judge_retries"] == 3


# ============================================================================
# _resolve_judges_from_config TESTS
# ============================================================================


@pytest.mark.integration
class TestResolveJudgesFromConfig:
    """Test judge configuration resolution."""

    def test_uses_top_level_judges(self):
        """Test that top-level judges list is used when present."""
        step = _make_step()
        judges = step._resolve_judges_from_config()

        assert len(judges) == 1
        assert judges[0]["identifier"] == "gpt-4-0613"
        assert judges[0]["type"] == "harmbench"

    def test_fallback_to_technique_params(self):
        """Test fallback when no top-level judges configured."""
        # Pass a config dict WITHOUT a judges key so the fallback path is exercised
        step = _make_step(config={"_no_judges": True})
        technique_params = {
            "judge": "ollama/tinyllama",
            "judge_type": "jailbreakbench",
        }
        judges = step._resolve_judges_from_config(technique_params=technique_params)

        assert len(judges) == 1
        assert judges[0]["identifier"] == "ollama/tinyllama"
        assert judges[0]["type"] == "jailbreakbench"

    def test_fallback_to_defaults_with_no_params(self):
        """Test fallback to default judge when nothing configured."""
        # Pass a config dict WITHOUT a judges key so the fallback path is exercised
        step = _make_step(config={"_no_judges": True})
        judges = step._resolve_judges_from_config()

        assert len(judges) == 1
        assert judges[0]["identifier"] == "gpt-4-0613"
        # default_type in _resolve_judges_from_config is "jailbreakbench"
        assert judges[0]["type"] == "jailbreakbench"

    def test_multiple_judges(self):
        """Test with multiple judges configured."""
        step = _make_step(
            config={
                "judges": [
                    {"identifier": "judge-1", "type": "harmbench"},
                    {"identifier": "judge-2", "type": "jailbreakbench"},
                    {"identifier": "judge-3", "type": "nuanced"},
                ],
            }
        )
        judges = step._resolve_judges_from_config()

        assert len(judges) == 3


# ============================================================================
# compute_best_score TESTS
# ============================================================================


@pytest.mark.integration
class TestComputeBestScore:
    """Test best score computation across judge columns."""

    def test_single_judge_score(self):
        """Test with single judge eval column."""
        step = _make_step()
        item = {"eval_hb": 1, "explanation_hb": "Harmful"}
        assert step.compute_best_score(item) == 1.0

    def test_multiple_judge_scores_takes_max(self):
        """Test that max score is returned across judges."""
        step = _make_step()
        item = {
            "eval_hb": 0,
            "eval_jb": 1,
            "eval_nj": 0,
        }
        assert step.compute_best_score(item) == 1.0

    def test_no_judge_columns(self):
        """Test with no judge columns present."""
        step = _make_step()
        item = {"goal": "test", "completion": "response"}
        assert step.compute_best_score(item) == 0.0

    def test_all_zero_scores(self):
        """Test with all scores being 0."""
        step = _make_step()
        item = {"eval_hb": 0, "eval_jb": 0, "eval_nj": 0}
        assert step.compute_best_score(item) == 0.0

    def test_none_values_handled(self):
        """Test that None values are handled gracefully."""
        step = _make_step()
        item = {"eval_hb": None, "eval_jb": 1}
        assert step.compute_best_score(item) == 1.0


# ============================================================================
# _enrich_items_with_scores TESTS
# ============================================================================


@pytest.mark.integration
class TestEnrichItemsWithScores:
    """Test score enrichment of data items."""

    def test_enriches_successful_items(self):
        """Test enrichment of items with judge scores."""
        step = _make_step()
        data = [
            {"eval_hb": 1},
            {"eval_hb": 0},
        ]
        step._enrich_items_with_scores(data)

        assert data[0]["best_score"] == 1.0
        assert data[0]["success"] is True
        assert data[1]["best_score"] == 0.0
        assert data[1]["success"] is False

    def test_error_indices_override(self):
        """Test that error indices get score 0 regardless."""
        step = _make_step()
        data = [
            {"eval_hb": 1},
        ]
        step._enrich_items_with_scores(data, error_indices={0})

        assert data[0]["best_score"] == 0.0
        assert data[0]["success"] is False


# ============================================================================
# _merge_evaluation_results TESTS
# ============================================================================


@pytest.mark.integration
class TestMergeEvaluationResults:
    """Test result merging from multiple judges."""

    def test_single_judge_merge(self):
        """Test merging results from a single judge."""
        step = _make_step()
        original = [
            {"goal": "g1", "prefix": "p1", "completion": "c1"},
        ]
        judge_results = {
            "harmbench": [
                {
                    "goal": "g1",
                    "prefix": "p1",
                    "completion": "c1",
                    "eval_hb": 1,
                    "explanation_hb": "Harmful",
                },
            ],
        }

        merged = step._merge_evaluation_results(original, judge_results)

        assert len(merged) == 1
        assert merged[0]["eval_hb"] == 1
        assert merged[0]["explanation_hb"] == "Harmful"

    def test_multi_judge_merge(self):
        """Test merging results from multiple judges."""
        step = _make_step()
        original = [
            {"goal": "g1", "prefix": "p1", "completion": "c1"},
        ]
        judge_results = {
            "harmbench": [
                {
                    "goal": "g1",
                    "prefix": "p1",
                    "completion": "c1",
                    "eval_hb": 1,
                    "explanation_hb": "Harmful",
                },
            ],
            "jailbreakbench": [
                {
                    "goal": "g1",
                    "prefix": "p1",
                    "completion": "c1",
                    "eval_jb": 0,
                    "explanation_jb": "Safe",
                },
            ],
        }

        merged = step._merge_evaluation_results(original, judge_results)

        assert merged[0]["eval_hb"] == 1
        assert merged[0]["eval_jb"] == 0

    def test_no_match_leaves_original_unchanged(self):
        """Test that unmatched rows keep original data."""
        step = _make_step()
        original = [
            {"goal": "g1", "prefix": "p1", "completion": "c1"},
        ]
        judge_results = {
            "harmbench": [
                {"goal": "different", "prefix": "p1", "completion": "c1", "eval_hb": 1},
            ],
        }

        merged = step._merge_evaluation_results(original, judge_results)

        assert "eval_hb" not in merged[0]

    def test_empty_judge_results(self):
        """Test merging with empty judge results."""
        step = _make_step()
        original = [{"goal": "g1", "prefix": "p1", "completion": "c1"}]

        merged = step._merge_evaluation_results(original, {})
        assert len(merged) == 1
        assert merged[0]["goal"] == "g1"


# ============================================================================
# _normalize_merge_key TESTS
# ============================================================================


@pytest.mark.integration
class TestNormalizeMergeKey:
    """Test merge key normalization."""

    def test_string_passthrough(self):
        """Test that strings pass through."""
        assert BaseEvaluationStep._normalize_merge_key("goal", "test") == "test"

    def test_none_becomes_empty_string(self):
        """Test that None becomes empty string for merge keys."""
        assert BaseEvaluationStep._normalize_merge_key("goal", None) == ""
        assert BaseEvaluationStep._normalize_merge_key("prefix", None) == ""
        assert BaseEvaluationStep._normalize_merge_key("completion", None) == ""

    def test_non_merge_key_passthrough(self):
        """Test that non-merge key values pass through as-is."""
        assert BaseEvaluationStep._normalize_merge_key("other", 42) == 42


# ============================================================================
# _prepare_judge_configs TESTS
# ============================================================================


@pytest.mark.integration
class TestPrepareJudgeConfigs:
    """Test judge configuration preparation."""

    def test_valid_judge_config(self):
        """Test preparing a valid judge configuration."""
        step = _make_step()
        judge_configs = [
            {
                "identifier": "gpt-4-0613",
                "type": "harmbench",
                "agent_type": "OPENAI_SDK",
            },
        ]
        prepared = step._prepare_judge_configs(judge_configs, {})

        assert len(prepared) == 1
        judge_type, config = prepared[0]
        assert judge_type == "harmbench"
        assert config["model_id"] == "gpt-4-0613"

    def test_skips_invalid_configs(self):
        """Test that invalid configs are skipped."""
        step = _make_step()
        judge_configs = [
            "not_a_dict",
            {"type": "unknown_evaluator_xyz"},
            {"identifier": "valid", "type": "harmbench"},
        ]
        prepared = step._prepare_judge_configs(judge_configs, {})

        # Only the last valid config should be included
        assert len(prepared) == 1

    def test_infers_type_from_identifier(self):
        """Test that judge type is inferred when not explicitly set."""
        step = _make_step()
        judge_configs = [
            {"identifier": "my-harmbench-judge"},
        ]
        prepared = step._prepare_judge_configs(judge_configs, {})

        assert len(prepared) == 1
        assert prepared[0][0] == "harmbench"

    def test_api_key_injection(self):
        """Test API key injection into agent_metadata."""
        step = _make_step()
        judge_configs = [
            {"identifier": "test", "type": "harmbench", "api_key": "sk-test123"},
        ]
        prepared = step._prepare_judge_configs(judge_configs, {})

        assert len(prepared) == 1
        config = prepared[0][1]
        assert config["agent_metadata"]["api_key"] == "sk-test123"


# ============================================================================
# _log_evaluation_asr TESTS
# ============================================================================


@pytest.mark.integration
class TestLogEvaluationAsr:
    """Test ASR logging."""

    def test_asr_logging_no_error_on_empty(self):
        """Test that logging with empty data doesn't error."""
        step = _make_step()
        # Should not raise
        step._log_evaluation_asr([])

    def test_asr_logging_with_data(self):
        """Test ASR logging with actual data."""
        step = _make_step()
        step._statistics["successful_judges"] = ["harmbench"]
        data = [
            {"eval_hb": 1, "best_score": 1.0},
            {"eval_hb": 0, "best_score": 0.0},
            {"eval_hb": 1, "best_score": 1.0},
        ]
        # Should not raise
        step._log_evaluation_asr(data)


# ============================================================================
# _build_judge_keys_from_data TESTS
# ============================================================================


@pytest.mark.integration
class TestBuildJudgeKeysFromData:
    """Test auto-detection of judge columns in data."""

    def test_detects_harmbench_columns(self):
        """Test detection of harmbench columns."""
        step = _make_step()
        data = [{"eval_hb": 1, "explanation_hb": "Harmful"}]

        keys = step._build_judge_keys_from_data(data)

        assert len(keys) == 1
        assert keys[0]["key"] == "eval_hb"
        assert keys[0]["explanation"] == "explanation_hb"
        assert keys[0]["label"] == "HarmBench"

    def test_detects_multiple_judges(self):
        """Test detection of multiple judge columns."""
        step = _make_step()
        data = [
            {
                "eval_hb": 1,
                "explanation_hb": "x",
                "eval_jb": 0,
                "explanation_jb": "y",
            }
        ]

        keys = step._build_judge_keys_from_data(data)
        assert len(keys) == 2

    def test_empty_data(self):
        """Test with empty data returns empty keys."""
        step = _make_step()
        keys = step._build_judge_keys_from_data([{}])
        assert len(keys) == 0


# ============================================================================
# STATISTICS TESTS
# ============================================================================


@pytest.mark.integration
class TestEvaluationStepStatistics:
    """Test statistics tracking."""

    def test_initial_statistics(self):
        """Test initial statistics are zeroed."""
        step = _make_step()
        stats = step.get_statistics()

        assert stats["input_count"] == 0
        assert stats["evaluated_count"] == 0
        assert stats["successful_judges"] == []
        assert stats["failed_judges"] == []

    def test_statistics_independence(self):
        """Test that get_statistics returns a copy."""
        step = _make_step()
        stats1 = step.get_statistics()
        stats1["input_count"] = 999

        stats2 = step.get_statistics()
        assert stats2["input_count"] == 0
