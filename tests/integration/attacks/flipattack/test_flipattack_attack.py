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
Integration tests for FlipAttack attack orchestration (attack.py).

Tests the FlipAttack class in hackagent.attacks.techniques.flipattack.attack
which extends BaseAttack and orchestrates the full pipeline:
generation → evaluation.

These tests verify:
- FlipAttack initialization with config merging
- Config validation
- Pipeline step definitions
- Full pipeline run with mocked sub-modules

Run with:
    pytest tests/integration/attacks/test_flipattack_attack.py --run-integration
"""

import copy
import logging
from unittest.mock import MagicMock, patch

import pytest

from hackagent.attacks.techniques.flipattack.attack import FlipAttack, _recursive_update
from hackagent.attacks.techniques.flipattack.config import DEFAULT_FLIPATTACK_CONFIG

logger = logging.getLogger(__name__)


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


@pytest.mark.integration
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


# ============================================================================
# FlipAttack INITIALIZATION TESTS
# ============================================================================


@pytest.mark.integration
class TestFlipAttackInitialization:
    """Test FlipAttack class initialization."""

    def test_requires_client(self):
        """Test that client is required."""
        with pytest.raises(ValueError, match="AuthenticatedClient must be provided"):
            FlipAttack(config={}, client=None, agent_router=_make_mock_router())

    def test_requires_agent_router(self):
        """Test that agent_router is required."""
        with pytest.raises(
            ValueError, match="Victim AgentRouter instance must be provided"
        ):
            FlipAttack(config={}, client=_make_mock_client(), agent_router=None)

    @patch("hackagent.attacks.techniques.base.BaseAttack.__init__", return_value=None)
    def test_merges_config_with_defaults(self, mock_base_init):
        """Test that user config is merged with DEFAULT_FLIPATTACK_CONFIG."""

        # The base __init__ should have been called with merged config
        call_args = mock_base_init.call_args
        merged_config = call_args[0][0]  # First positional arg

        # User's flip_mode should override default
        assert merged_config["flipattack_params"]["flip_mode"] == "FWO"
        # Other defaults should be preserved
        assert merged_config["attack_type"] == "flipattack"
        assert merged_config["flipattack_params"]["cot"] is False

    @patch("hackagent.attacks.techniques.base.BaseAttack.__init__", return_value=None)
    def test_default_config_not_mutated(self, mock_base_init):
        """Test that creating FlipAttack doesn't mutate DEFAULT_FLIPATTACK_CONFIG."""
        original_mode = DEFAULT_FLIPATTACK_CONFIG["flipattack_params"]["flip_mode"]

        FlipAttack(
            config={"flipattack_params": {"flip_mode": "FWO"}},
            client=_make_mock_client(),
            agent_router=_make_mock_router(),
        )

        assert (
            DEFAULT_FLIPATTACK_CONFIG["flipattack_params"]["flip_mode"] == original_mode
        )


# ============================================================================
# CONFIG VALIDATION TESTS
# ============================================================================


@pytest.mark.integration
class TestFlipAttackValidation:
    """Test FlipAttack configuration validation."""

    @patch("hackagent.attacks.techniques.base.BaseAttack.__init__", return_value=None)
    @patch("hackagent.attacks.techniques.base.BaseAttack._validate_config")
    def test_validate_config_checks_required_keys(
        self, mock_super_validate, mock_base_init
    ):
        """Test that _validate_config checks for required keys."""
        fa = FlipAttack(
            config={"flipattack_params": {"flip_mode": "FCS"}, "goals": ["test"]},
            client=_make_mock_client(),
            agent_router=_make_mock_router(),
        )

        # Give it a config missing required keys
        fa.config = {"attack_type": "flipattack"}

        with pytest.raises(ValueError, match="missing required keys"):
            fa._validate_config()

    @patch("hackagent.attacks.techniques.base.BaseAttack.__init__", return_value=None)
    @patch("hackagent.attacks.techniques.base.BaseAttack._validate_config")
    def test_validate_config_rejects_invalid_flip_mode(
        self, mock_super_validate, mock_base_init
    ):
        """Test that _validate_config rejects invalid flip_mode."""
        fa = FlipAttack(
            config={},
            client=_make_mock_client(),
            agent_router=_make_mock_router(),
        )

        fa.config = {
            "attack_type": "flipattack",
            "flipattack_params": {"flip_mode": "INVALID"},
            "goals": ["test"],
            "output_dir": "./logs",
        }

        with pytest.raises(ValueError, match="flip_mode must be one of"):
            fa._validate_config()

    @pytest.mark.parametrize("mode", ["FWO", "FCW", "FCS", "FMM"])
    @patch("hackagent.attacks.techniques.base.BaseAttack.__init__", return_value=None)
    @patch("hackagent.attacks.techniques.base.BaseAttack._validate_config")
    def test_validate_config_accepts_valid_modes(
        self, mock_super_validate, mock_base_init, mode
    ):
        """Test that _validate_config accepts all valid flip modes."""
        fa = FlipAttack(
            config={},
            client=_make_mock_client(),
            agent_router=_make_mock_router(),
        )

        fa.config = {
            "attack_type": "flipattack",
            "flipattack_params": {"flip_mode": mode},
            "goals": ["test"],
            "output_dir": "./logs",
        }

        # Should not raise
        fa._validate_config()


# ============================================================================
# PIPELINE STEPS TESTS
# ============================================================================


@pytest.mark.integration
class TestFlipAttackPipelineSteps:
    """Test pipeline step definitions."""

    @patch("hackagent.attacks.techniques.base.BaseAttack.__init__", return_value=None)
    def test_get_pipeline_steps_returns_two_steps(self, mock_base_init):
        """Test that pipeline has generation and evaluation steps."""
        fa = FlipAttack(
            config={},
            client=_make_mock_client(),
            agent_router=_make_mock_router(),
        )
        fa.config = copy.deepcopy(DEFAULT_FLIPATTACK_CONFIG)

        steps = fa._get_pipeline_steps()

        assert len(steps) == 2

    @patch("hackagent.attacks.techniques.base.BaseAttack.__init__", return_value=None)
    def test_pipeline_step_names(self, mock_base_init):
        """Test pipeline step name convention."""
        fa = FlipAttack(
            config={},
            client=_make_mock_client(),
            agent_router=_make_mock_router(),
        )
        fa.config = copy.deepcopy(DEFAULT_FLIPATTACK_CONFIG)

        steps = fa._get_pipeline_steps()

        assert "Generation" in steps[0]["name"]
        assert "Evaluation" in steps[1]["name"]

    @patch("hackagent.attacks.techniques.base.BaseAttack.__init__", return_value=None)
    def test_pipeline_step_types(self, mock_base_init):
        """Test pipeline step type enums."""
        fa = FlipAttack(
            config={},
            client=_make_mock_client(),
            agent_router=_make_mock_router(),
        )
        fa.config = copy.deepcopy(DEFAULT_FLIPATTACK_CONFIG)

        steps = fa._get_pipeline_steps()

        assert steps[0]["step_type_enum"] == "GENERATION"
        assert steps[1]["step_type_enum"] == "EVALUATION"

    @patch("hackagent.attacks.techniques.base.BaseAttack.__init__", return_value=None)
    def test_pipeline_step_functions(self, mock_base_init):
        """Test that pipeline steps reference correct functions."""
        from hackagent.attacks.techniques.flipattack import generation, evaluation

        fa = FlipAttack(
            config={},
            client=_make_mock_client(),
            agent_router=_make_mock_router(),
        )
        fa.config = copy.deepcopy(DEFAULT_FLIPATTACK_CONFIG)

        steps = fa._get_pipeline_steps()

        assert steps[0]["function"] is generation.execute
        assert steps[1]["function"] is evaluation.execute

    @patch("hackagent.attacks.techniques.base.BaseAttack.__init__", return_value=None)
    def test_generation_step_config_keys(self, mock_base_init):
        """Test generation step pulls correct config keys."""
        fa = FlipAttack(
            config={},
            client=_make_mock_client(),
            agent_router=_make_mock_router(),
        )
        fa.config = copy.deepcopy(DEFAULT_FLIPATTACK_CONFIG)

        steps = fa._get_pipeline_steps()
        gen_config_keys = steps[0]["config_keys"]

        assert "flipattack_params" in gen_config_keys
        assert "_run_id" in gen_config_keys
        assert "_tracker" in gen_config_keys

    @patch("hackagent.attacks.techniques.base.BaseAttack.__init__", return_value=None)
    def test_evaluation_step_config_keys(self, mock_base_init):
        """Test evaluation step pulls correct config keys."""
        fa = FlipAttack(
            config={},
            client=_make_mock_client(),
            agent_router=_make_mock_router(),
        )
        fa.config = copy.deepcopy(DEFAULT_FLIPATTACK_CONFIG)

        steps = fa._get_pipeline_steps()
        eval_config_keys = steps[1]["config_keys"]

        assert "flipattack_params" in eval_config_keys
        assert "judges" in eval_config_keys
        assert "batch_size_judge" in eval_config_keys
        assert "max_new_tokens_eval" in eval_config_keys
