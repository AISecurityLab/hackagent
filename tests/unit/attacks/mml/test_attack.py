# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Unit tests for MML attack class (attack.py).

Tests the MMLAttack class initialization, config validation,
pipeline step definitions, and run method orchestration.
"""

import copy
from unittest.mock import MagicMock, patch

import pytest

from hackagent.attacks.techniques.mml.attack import MMLAttack, _recursive_update
from hackagent.attacks.techniques.mml.config import DEFAULT_MML_CONFIG


# ============================================================================
# HELPERS
# ============================================================================


def _make_mock_client():
    """Create a mock AuthenticatedClient."""
    client = MagicMock()
    client._base_url = "https://api.hackagent.dev"
    client.token = "test-token"
    return client


def _make_mock_router():
    """Create a mock AgentRouter."""
    router = MagicMock()
    router.backend_agent = MagicMock()
    router.backend_agent.id = "test-agent-id"
    return router


# ============================================================================
# _recursive_update TESTS
# ============================================================================


class TestRecursiveUpdate:
    """Test the _recursive_update helper function."""

    def test_simple_overwrite(self):
        """Test simple key overwriting."""
        target = {"a": 1, "b": 2}
        source = {"b": 3, "c": 4}
        _recursive_update(target, source)

        assert target["a"] == 1
        assert target["b"] == 3
        assert target["c"] == 4

    def test_nested_dict_merge(self):
        """Test nested dictionary merging."""
        target = {"params": {"a": 1, "b": 2}}
        source = {"params": {"b": 3, "c": 4}}
        _recursive_update(target, source)

        assert target["params"]["a"] == 1
        assert target["params"]["b"] == 3
        assert target["params"]["c"] == 4

    def test_deep_nested_merge(self):
        """Test deeply nested merge."""
        target = {"level1": {"level2": {"a": 1}}}
        source = {"level1": {"level2": {"b": 2}}}
        _recursive_update(target, source)

        assert target["level1"]["level2"]["a"] == 1
        assert target["level1"]["level2"]["b"] == 2

    def test_internal_keys_by_reference(self):
        """Test that keys starting with '_' are passed by reference."""
        tracker = MagicMock()
        target = {}
        source = {"_tracker": tracker, "normal_key": "value"}
        _recursive_update(target, source)

        assert target["_tracker"] is tracker  # Same object, not deep copy
        assert target["normal_key"] == "value"

    def test_overwrite_non_dict_with_dict(self):
        """Test overwriting a non-dict with a dict."""
        target = {"key": "string_value"}
        source = {"key": {"nested": True}}
        _recursive_update(target, source)

        assert isinstance(target["key"], dict)
        assert target["key"]["nested"] is True

    def test_empty_source(self):
        """Test with empty source dict."""
        target = {"a": 1}
        _recursive_update(target, {})
        assert target == {"a": 1}

    def test_empty_target(self):
        """Test with empty target dict."""
        target = {}
        source = {"a": 1, "b": {"c": 2}}
        _recursive_update(target, source)
        assert target["a"] == 1
        assert target["b"]["c"] == 2


# ============================================================================
# MMLAttack INITIALIZATION TESTS
# ============================================================================


class TestMMLAttackInitialization:
    """Test MMLAttack class initialization."""

    def test_requires_client(self):
        """Test that client is required."""
        with pytest.raises(ValueError, match="AuthenticatedClient must be provided"):
            MMLAttack(config={}, client=None, agent_router=_make_mock_router())

    def test_requires_agent_router(self):
        """Test that agent_router is required."""
        with pytest.raises(
            ValueError, match="Victim AgentRouter instance must be provided"
        ):
            MMLAttack(config={}, client=_make_mock_client(), agent_router=None)

    @patch("hackagent.attacks.techniques.base.BaseAttack.__init__", return_value=None)
    def test_merges_config_with_defaults(self, mock_base_init):
        """Test that user config is merged with DEFAULT_MML_CONFIG."""
        MMLAttack(
            config={"mml_params": {"encoding_mode": "mirror"}},
            client=_make_mock_client(),
            agent_router=_make_mock_router(),
        )

        call_args = mock_base_init.call_args
        merged_config = call_args[0][0]

        assert merged_config["mml_params"]["encoding_mode"] == "mirror"
        assert merged_config["attack_type"] == "mml"
        # Other defaults should be preserved
        assert merged_config["mml_params"]["image_width"] == 800
        assert merged_config["mml_params"]["prompt_style"] == "game"

    @patch("hackagent.attacks.techniques.base.BaseAttack.__init__", return_value=None)
    def test_default_config_not_mutated(self, mock_base_init):
        """Test that creating MMLAttack doesn't mutate DEFAULT_MML_CONFIG."""
        original_mode = DEFAULT_MML_CONFIG["mml_params"]["encoding_mode"]

        MMLAttack(
            config={"mml_params": {"encoding_mode": "rotate"}},
            client=_make_mock_client(),
            agent_router=_make_mock_router(),
        )

        assert DEFAULT_MML_CONFIG["mml_params"]["encoding_mode"] == original_mode

    @patch("hackagent.attacks.techniques.base.BaseAttack.__init__", return_value=None)
    def test_sets_logger(self, mock_base_init):
        """Test that logger is set with correct name."""
        attack = MMLAttack(
            config={},
            client=_make_mock_client(),
            agent_router=_make_mock_router(),
        )

        assert attack.logger.name == "hackagent.attacks.mml"


# ============================================================================
# SETUP ALGORITHM TESTS
# ============================================================================


class TestMMLAttackSetupAlgorithm:
    """Test _setup_algorithm method."""

    @patch("hackagent.attacks.techniques.base.BaseAttack.__init__", return_value=None)
    def test_default_encoding_mode(self, mock_base_init):
        """Test default encoding mode is set."""
        attack = MMLAttack(
            config={},
            client=_make_mock_client(),
            agent_router=_make_mock_router(),
        )
        attack.config = copy.deepcopy(DEFAULT_MML_CONFIG)
        attack._setup_algorithm()

        assert attack.encoding_mode == "word_replacement"

    @patch("hackagent.attacks.techniques.base.BaseAttack.__init__", return_value=None)
    def test_custom_encoding_mode(self, mock_base_init):
        """Test custom encoding mode is read from config."""
        attack = MMLAttack(
            config={},
            client=_make_mock_client(),
            agent_router=_make_mock_router(),
        )
        attack.config = {
            "mml_params": {"encoding_mode": "base64", "prompt_style": "control"}
        }
        attack._setup_algorithm()

        assert attack.encoding_mode == "base64"
        assert attack.prompt_style == "control"

    @patch("hackagent.attacks.techniques.base.BaseAttack.__init__", return_value=None)
    def test_missing_mml_params_uses_defaults(self, mock_base_init):
        """Test that missing mml_params falls back to defaults."""
        attack = MMLAttack(
            config={},
            client=_make_mock_client(),
            agent_router=_make_mock_router(),
        )
        attack.config = {}
        attack._setup_algorithm()

        assert attack.encoding_mode == "word_replacement"
        assert attack.prompt_style == "game"


# ============================================================================
# VLM VALIDATION TESTS
# ============================================================================


class TestMMLAttackVLMWarning:
    """Test _warn_if_not_vlm warning logic."""

    @patch("hackagent.attacks.techniques.base.BaseAttack.__init__", return_value=None)
    def test_no_warning_for_known_vlm(self, mock_base_init):
        """Test no warning is emitted for known VLM model names."""
        attack = MMLAttack(
            config={},
            client=_make_mock_client(),
            agent_router=_make_mock_router(),
        )
        attack.logger = MagicMock()
        router = _make_mock_router()
        router.backend_agent.metadata = {"name": "gpt-4o"}
        attack.agent_router = router

        attack._warn_if_not_vlm()

        attack.logger.warning.assert_not_called()

    @patch("hackagent.attacks.techniques.base.BaseAttack.__init__", return_value=None)
    def test_warning_for_text_only_model(self, mock_base_init):
        """Test warning is emitted for text-only model names."""
        attack = MMLAttack(
            config={},
            client=_make_mock_client(),
            agent_router=_make_mock_router(),
        )
        attack.logger = MagicMock()
        router = _make_mock_router()
        router.backend_agent.metadata = {"name": "llama-3-8b"}
        attack.agent_router = router

        attack._warn_if_not_vlm()

        attack.logger.warning.assert_called_once()
        warning_msg = attack.logger.warning.call_args[0][0]
        assert "llama-3-8b" in warning_msg
        assert "VLM" in warning_msg

    @patch("hackagent.attacks.techniques.base.BaseAttack.__init__", return_value=None)
    def test_warning_when_no_metadata(self, mock_base_init):
        """Test warning is emitted when model name cannot be determined."""
        attack = MMLAttack(
            config={},
            client=_make_mock_client(),
            agent_router=_make_mock_router(),
        )
        attack.logger = MagicMock()
        router = _make_mock_router()
        router.backend_agent.metadata = {}
        attack.agent_router = router

        attack._warn_if_not_vlm()

        attack.logger.warning.assert_called_once()
        warning_msg = attack.logger.warning.call_args[0][0]
        assert "Could not determine" in warning_msg

    @pytest.mark.parametrize(
        "model_name",
        [
            "qwen-vl-max",
            "qwen2.5-vl-72b",
            "llava-v1.6-34b",
            "gemini-1.5-pro",
            "claude-3-opus",
            "internvl2-26b",
            "phi-3-vision-128k",
            "pixtral-12b",
        ],
    )
    @patch("hackagent.attacks.techniques.base.BaseAttack.__init__", return_value=None)
    def test_no_warning_for_various_vlms(self, mock_base_init, model_name):
        """Test no warning for various known VLM model names."""
        attack = MMLAttack(
            config={},
            client=_make_mock_client(),
            agent_router=_make_mock_router(),
        )
        attack.logger = MagicMock()
        router = _make_mock_router()
        router.backend_agent.metadata = {"name": model_name}
        attack.agent_router = router

        attack._warn_if_not_vlm()

        attack.logger.warning.assert_not_called()


# ============================================================================
# CONFIG VALIDATION TESTS
# ============================================================================


class TestMMLAttackValidation:
    """Test MMLAttack configuration validation."""

    @patch("hackagent.attacks.techniques.base.BaseAttack.__init__", return_value=None)
    @patch("hackagent.attacks.techniques.base.BaseAttack._validate_config")
    def test_validate_config_checks_required_keys(
        self, mock_super_validate, mock_base_init
    ):
        """Test that _validate_config checks for required keys."""
        attack = MMLAttack(
            config={},
            client=_make_mock_client(),
            agent_router=_make_mock_router(),
        )
        attack.config = {"attack_type": "mml"}

        with pytest.raises(ValueError, match="missing required keys"):
            attack._validate_config()

    @patch("hackagent.attacks.techniques.base.BaseAttack.__init__", return_value=None)
    @patch("hackagent.attacks.techniques.base.BaseAttack._validate_config")
    def test_validate_config_rejects_invalid_encoding_mode(
        self, mock_super_validate, mock_base_init
    ):
        """Test that _validate_config rejects invalid encoding_mode."""
        attack = MMLAttack(
            config={},
            client=_make_mock_client(),
            agent_router=_make_mock_router(),
        )
        attack.config = {
            "attack_type": "mml",
            "mml_params": {"encoding_mode": "INVALID"},
            "goals": ["test"],
            "output_dir": "./logs",
        }

        with pytest.raises(ValueError, match="encoding_mode must be one of"):
            attack._validate_config()

    @pytest.mark.parametrize(
        "mode", ["word_replacement", "mirror", "rotate", "base64", "mixed"]
    )
    @patch("hackagent.attacks.techniques.base.BaseAttack.__init__", return_value=None)
    @patch("hackagent.attacks.techniques.base.BaseAttack._validate_config")
    def test_validate_config_accepts_valid_modes(
        self, mock_super_validate, mock_base_init, mode
    ):
        """Test that _validate_config accepts all valid encoding modes."""
        attack = MMLAttack(
            config={},
            client=_make_mock_client(),
            agent_router=_make_mock_router(),
        )
        attack.config = {
            "attack_type": "mml",
            "mml_params": {"encoding_mode": mode},
            "goals": ["test"],
            "output_dir": "./logs",
        }

        # Should not raise
        attack._validate_config()

    @patch("hackagent.attacks.techniques.base.BaseAttack.__init__", return_value=None)
    @patch("hackagent.attacks.techniques.base.BaseAttack._validate_config")
    def test_validate_config_valid_full_config(
        self, mock_super_validate, mock_base_init
    ):
        """Test that full valid config passes validation."""
        attack = MMLAttack(
            config={},
            client=_make_mock_client(),
            agent_router=_make_mock_router(),
        )
        attack.config = copy.deepcopy(DEFAULT_MML_CONFIG)
        attack.config["goals"] = ["test goal"]
        attack.config["output_dir"] = "/tmp/test"

        # Should not raise
        attack._validate_config()


# ============================================================================
# PIPELINE STEPS TESTS
# ============================================================================


class TestMMLAttackPipelineSteps:
    """Test pipeline step definitions."""

    @patch("hackagent.attacks.techniques.base.BaseAttack.__init__", return_value=None)
    def test_get_pipeline_steps_returns_two_steps(self, mock_base_init):
        """Test that pipeline has generation and evaluation steps."""
        attack = MMLAttack(
            config={},
            client=_make_mock_client(),
            agent_router=_make_mock_router(),
        )
        attack.config = copy.deepcopy(DEFAULT_MML_CONFIG)

        steps = attack._get_pipeline_steps()

        assert len(steps) == 2

    @patch("hackagent.attacks.techniques.base.BaseAttack.__init__", return_value=None)
    def test_pipeline_step_names(self, mock_base_init):
        """Test pipeline step name convention."""
        attack = MMLAttack(
            config={},
            client=_make_mock_client(),
            agent_router=_make_mock_router(),
        )
        attack.config = copy.deepcopy(DEFAULT_MML_CONFIG)

        steps = attack._get_pipeline_steps()

        assert "Generation" in steps[0]["name"]
        assert "Evaluation" in steps[1]["name"]

    @patch("hackagent.attacks.techniques.base.BaseAttack.__init__", return_value=None)
    def test_pipeline_step_types(self, mock_base_init):
        """Test pipeline step type enums."""
        attack = MMLAttack(
            config={},
            client=_make_mock_client(),
            agent_router=_make_mock_router(),
        )
        attack.config = copy.deepcopy(DEFAULT_MML_CONFIG)

        steps = attack._get_pipeline_steps()

        assert steps[0]["step_type_enum"] == "GENERATION"
        assert steps[1]["step_type_enum"] == "EVALUATION"

    @patch("hackagent.attacks.techniques.base.BaseAttack.__init__", return_value=None)
    def test_pipeline_step_functions(self, mock_base_init):
        """Test that pipeline steps reference correct functions."""
        from hackagent.attacks.techniques.mml import evaluation, generation

        attack = MMLAttack(
            config={},
            client=_make_mock_client(),
            agent_router=_make_mock_router(),
        )
        attack.config = copy.deepcopy(DEFAULT_MML_CONFIG)

        steps = attack._get_pipeline_steps()

        assert steps[0]["function"] is generation.execute
        assert steps[1]["function"] is evaluation.execute

    @patch("hackagent.attacks.techniques.base.BaseAttack.__init__", return_value=None)
    def test_generation_step_config_keys(self, mock_base_init):
        """Test generation step pulls correct config keys."""
        attack = MMLAttack(
            config={},
            client=_make_mock_client(),
            agent_router=_make_mock_router(),
        )
        attack.config = copy.deepcopy(DEFAULT_MML_CONFIG)

        steps = attack._get_pipeline_steps()
        gen_config_keys = steps[0]["config_keys"]

        assert "mml_params" in gen_config_keys
        assert "_run_id" in gen_config_keys
        assert "_tracker" in gen_config_keys
        assert "batch_size" in gen_config_keys

    @patch("hackagent.attacks.techniques.base.BaseAttack.__init__", return_value=None)
    def test_evaluation_step_config_keys(self, mock_base_init):
        """Test evaluation step pulls correct config keys."""
        attack = MMLAttack(
            config={},
            client=_make_mock_client(),
            agent_router=_make_mock_router(),
        )
        attack.config = copy.deepcopy(DEFAULT_MML_CONFIG)

        steps = attack._get_pipeline_steps()
        eval_config_keys = steps[1]["config_keys"]

        assert "mml_params" in eval_config_keys
        assert "judges" in eval_config_keys
        assert "batch_size_judge" in eval_config_keys
        assert "max_tokens_eval" in eval_config_keys

    @patch("hackagent.attacks.techniques.base.BaseAttack.__init__", return_value=None)
    def test_generation_step_required_args(self, mock_base_init):
        """Test generation step required args."""
        attack = MMLAttack(
            config={},
            client=_make_mock_client(),
            agent_router=_make_mock_router(),
        )
        attack.config = copy.deepcopy(DEFAULT_MML_CONFIG)

        steps = attack._get_pipeline_steps()

        assert "logger" in steps[0]["required_args"]
        assert "agent_router" in steps[0]["required_args"]
        assert "config" in steps[0]["required_args"]

    @patch("hackagent.attacks.techniques.base.BaseAttack.__init__", return_value=None)
    def test_evaluation_step_required_args(self, mock_base_init):
        """Test evaluation step required args."""
        attack = MMLAttack(
            config={},
            client=_make_mock_client(),
            agent_router=_make_mock_router(),
        )
        attack.config = copy.deepcopy(DEFAULT_MML_CONFIG)

        steps = attack._get_pipeline_steps()

        assert "logger" in steps[1]["required_args"]
        assert "config" in steps[1]["required_args"]
        assert "client" in steps[1]["required_args"]


# ============================================================================
# RUN METHOD TESTS
# ============================================================================


class TestMMLAttackRun:
    """Test the run method orchestration."""

    @patch("hackagent.attacks.techniques.base.BaseAttack.__init__", return_value=None)
    def test_run_returns_empty_list_for_no_goals(self, mock_base_init):
        """Test that run() returns [] when goals is empty."""
        attack = MMLAttack(
            config={},
            client=_make_mock_client(),
            agent_router=_make_mock_router(),
        )
        attack.config = copy.deepcopy(DEFAULT_MML_CONFIG)

        result = attack.run([])
        assert result == []

    @patch("hackagent.attacks.techniques.base.BaseAttack.__init__", return_value=None)
    @patch("hackagent.attacks.techniques.mml.attack.MMLAttack._initialize_coordinator")
    @patch("hackagent.attacks.techniques.mml.attack.MMLAttack._execute_pipeline")
    def test_run_calls_pipeline(self, mock_execute, mock_coordinator, mock_base_init):
        """Test that run() invokes the pipeline with goals."""
        mock_coord = MagicMock()
        mock_coord.goal_tracker = MagicMock()
        mock_coordinator.return_value = mock_coord
        mock_execute.return_value = [{"goal": "test", "success": True}]

        attack = MMLAttack(
            config={},
            client=_make_mock_client(),
            agent_router=_make_mock_router(),
        )
        attack.config = copy.deepcopy(DEFAULT_MML_CONFIG)

        results = attack.run(["test goal"])

        mock_coordinator.assert_called_once()
        mock_execute.assert_called_once()
        assert results == [{"goal": "test", "success": True}]

    @patch("hackagent.attacks.techniques.base.BaseAttack.__init__", return_value=None)
    @patch("hackagent.attacks.techniques.mml.attack.MMLAttack._initialize_coordinator")
    @patch("hackagent.attacks.techniques.mml.attack.MMLAttack._execute_pipeline")
    def test_run_finalizes_coordinator(
        self, mock_execute, mock_coordinator, mock_base_init
    ):
        """Test that run() finalizes the coordinator."""
        mock_coord = MagicMock()
        mock_coord.goal_tracker = MagicMock()
        mock_coordinator.return_value = mock_coord
        mock_execute.return_value = [{"goal": "g1"}]

        attack = MMLAttack(
            config={},
            client=_make_mock_client(),
            agent_router=_make_mock_router(),
        )
        attack.config = copy.deepcopy(DEFAULT_MML_CONFIG)

        attack.run(["g1"])

        mock_coord.finalize_all_goals.assert_called_once()
        mock_coord.log_summary.assert_called_once()
        mock_coord.finalize_pipeline.assert_called_once()

    @patch("hackagent.attacks.techniques.base.BaseAttack.__init__", return_value=None)
    @patch("hackagent.attacks.techniques.mml.attack.MMLAttack._initialize_coordinator")
    @patch("hackagent.attacks.techniques.mml.attack.MMLAttack._execute_pipeline")
    def test_run_crash_safe_on_exception(
        self, mock_execute, mock_coordinator, mock_base_init
    ):
        """Test that run() calls finalize_on_error on exception."""
        mock_coord = MagicMock()
        mock_coord.goal_tracker = MagicMock()
        mock_coordinator.return_value = mock_coord
        mock_execute.side_effect = RuntimeError("Pipeline exploded")

        attack = MMLAttack(
            config={},
            client=_make_mock_client(),
            agent_router=_make_mock_router(),
        )
        attack.config = copy.deepcopy(DEFAULT_MML_CONFIG)

        with pytest.raises(RuntimeError, match="Pipeline exploded"):
            attack.run(["goal"])

        mock_coord.finalize_on_error.assert_called_once()

    @patch("hackagent.attacks.techniques.base.BaseAttack.__init__", return_value=None)
    @patch("hackagent.attacks.techniques.mml.attack.MMLAttack._initialize_coordinator")
    @patch("hackagent.attacks.techniques.mml.attack.MMLAttack._execute_pipeline")
    def test_run_passes_goal_metadata(
        self, mock_execute, mock_coordinator, mock_base_init
    ):
        """Test that run() passes encoding/prompt metadata to coordinator."""
        mock_coord = MagicMock()
        mock_coord.goal_tracker = MagicMock()
        mock_coordinator.return_value = mock_coord
        mock_execute.return_value = []

        attack = MMLAttack(
            config={},
            client=_make_mock_client(),
            agent_router=_make_mock_router(),
        )
        attack.config = copy.deepcopy(DEFAULT_MML_CONFIG)
        attack.config["mml_params"]["encoding_mode"] = "base64"
        attack.config["mml_params"]["prompt_style"] = "control"

        attack.run(["goal"])

        call_kwargs = mock_coordinator.call_args[1]
        assert call_kwargs["initial_metadata"]["encoding_mode"] == "base64"
        assert call_kwargs["initial_metadata"]["prompt_style"] == "control"

    @patch("hackagent.attacks.techniques.base.BaseAttack.__init__", return_value=None)
    @patch("hackagent.attacks.techniques.mml.attack.MMLAttack._initialize_coordinator")
    @patch("hackagent.attacks.techniques.mml.attack.MMLAttack._execute_pipeline")
    def test_run_returns_empty_list_on_none_result(
        self, mock_execute, mock_coordinator, mock_base_init
    ):
        """Test that run() returns [] when pipeline returns None."""
        mock_coord = MagicMock()
        mock_coord.goal_tracker = MagicMock()
        mock_coordinator.return_value = mock_coord
        mock_execute.return_value = None

        attack = MMLAttack(
            config={},
            client=_make_mock_client(),
            agent_router=_make_mock_router(),
        )
        attack.config = copy.deepcopy(DEFAULT_MML_CONFIG)

        results = attack.run(["goal"])
        assert results == []
