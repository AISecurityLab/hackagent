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
Integration tests for FlipAttack configuration (config.py).

Tests FlipAttackParams, FlipAttackConfig, and DEFAULT_FLIPATTACK_CONFIG
to verify proper config creation, validation, serialization roundtrips,
and merging behavior.

Run with:
    pytest tests/integration/attacks/test_flipattack_config.py --run-integration
"""

import copy
import logging

import pytest

from hackagent.attacks.techniques.flipattack.config import (
    DEFAULT_FLIPATTACK_CONFIG,
    FlipAttackConfig,
    FlipAttackParams,
)

logger = logging.getLogger(__name__)


# ============================================================================
# FlipAttackParams TESTS
# ============================================================================


@pytest.mark.integration
class TestFlipAttackParams:
    """Test FlipAttackParams dataclass."""

    def test_default_params(self):
        """Test default parameter values."""
        params = FlipAttackParams()
        assert params.flip_mode == "FCS"
        assert params.cot is False
        assert params.lang_gpt is False
        assert params.few_shot is False

    @pytest.mark.parametrize("mode", ["FWO", "FCW", "FCS", "FMM"])
    def test_valid_flip_modes(self, mode):
        """Test all valid flip modes are accepted."""
        params = FlipAttackParams(flip_mode=mode)
        assert params.flip_mode == mode

    def test_invalid_flip_mode_raises(self):
        """Test that invalid flip mode raises ValueError."""
        with pytest.raises(ValueError, match="flip_mode must be one of"):
            FlipAttackParams(flip_mode="INVALID")

    def test_all_enhancements_enabled(self):
        """Test creating params with all enhancements."""
        params = FlipAttackParams(
            flip_mode="FCS", cot=True, lang_gpt=True, few_shot=True
        )
        assert params.cot is True
        assert params.lang_gpt is True
        assert params.few_shot is True


# ============================================================================
# FlipAttackConfig TESTS
# ============================================================================


@pytest.mark.integration
class TestFlipAttackConfig:
    """Test FlipAttackConfig dataclass and serialization."""

    def test_default_config(self):
        """Test default configuration values."""
        config = FlipAttackConfig()
        assert config.attack_type == "flipattack"
        assert config.batch_size_judge == 1
        assert config.max_new_tokens_eval == 256
        assert config.filter_len == 10
        assert config.judge_request_timeout == 120
        assert config.judge_temperature == 0.0
        assert config.max_judge_retries == 1
        assert config.output_dir == "./logs/flipattack"
        assert config.start_step == 1
        assert config.goals == []
        assert config.judges == []
        assert config.dataset is None

    def test_from_dict_basic(self):
        """Test creating config from a basic dictionary."""
        config_dict = {
            "attack_type": "flipattack",
            "goals": ["Test goal 1", "Test goal 2"],
            "flipattack_params": {"flip_mode": "FWO", "cot": True},
        }
        config = FlipAttackConfig.model_validate(config_dict)

        assert config.attack_type == "flipattack"
        assert config.goals == ["Test goal 1", "Test goal 2"]
        assert config.flipattack_params.flip_mode == "FWO"
        assert config.flipattack_params.cot is True

    def test_from_dict_with_judges(self):
        """Test creating config with judge configurations."""
        config_dict = {
            "attack_type": "flipattack",
            "goals": ["Test"],
            "judges": [
                {"identifier": "gpt-4-0613", "type": "harmbench"},
                {"identifier": "gpt-4-0613", "type": "jailbreakbench"},
            ],
        }
        config = FlipAttackConfig.model_validate(config_dict)

        assert len(config.judges) == 2
        assert config.judges[0]["type"] == "harmbench"
        assert config.judges[1]["type"] == "jailbreakbench"

    def test_to_dict_roundtrip(self):
        """Test config serialization roundtrip (from_dict → to_dict)."""
        original = {
            "attack_type": "flipattack",
            "flipattack_params": {
                "flip_mode": "FCW",
                "cot": True,
                "lang_gpt": False,
                "few_shot": True,
            },
            "goals": ["goal1"],
            "judges": [{"identifier": "test-judge", "type": "harmbench"}],
            "batch_size_judge": 4,
            "max_new_tokens_eval": 512,
            "filter_len": 20,
            "judge_request_timeout": 60,
            "judge_temperature": 0.1,
            "max_judge_retries": 3,
            "dataset": "advbench",
            "output_dir": "/tmp/test",
            "start_step": 2,
        }
        config = FlipAttackConfig.model_validate(original)
        result = config.model_dump(by_alias=True, mode="json", exclude_none=True)

        assert result["attack_type"] == "flipattack"
        assert result["flipattack_params"]["flip_mode"] == "FCW"
        assert result["flipattack_params"]["cot"] is True
        assert result["flipattack_params"]["few_shot"] is True
        assert result["goals"] == ["goal1"]
        assert result["batch_size_judge"] == 4
        assert result["max_new_tokens_eval"] == 512
        assert result["dataset"] == "advbench"
        assert result["output_dir"] == "/tmp/test"
        assert result["start_step"] == 2

    def test_from_dict_missing_keys_uses_defaults(self):
        """Test that missing keys fallback to defaults."""
        config = FlipAttackConfig.model_validate({})

        assert config.attack_type == "flipattack"
        assert config.goals == []
        assert config.flipattack_params.flip_mode == "FCS"
        assert config.batch_size_judge == 1

    def test_from_dict_extra_keys_ignored(self):
        """Test that extra keys in dict are ignored without error."""
        config_dict = {
            "attack_type": "flipattack",
            "unknown_key": "should_be_ignored",
            "another_unknown": 42,
        }
        config = FlipAttackConfig.model_validate(config_dict)
        assert config.attack_type == "flipattack"


# ============================================================================
# DEFAULT_FLIPATTACK_CONFIG TESTS
# ============================================================================


@pytest.mark.integration
class TestDefaultFlipAttackConfig:
    """Test the DEFAULT_FLIPATTACK_CONFIG dictionary."""

    def test_default_config_has_required_keys(self):
        """Test default config contains all required keys."""
        required_keys = [
            "attack_type",
            "flipattack_params",
            "judges",
            "goals",
            "output_dir",
            "start_step",
        ]
        for key in required_keys:
            assert key in DEFAULT_FLIPATTACK_CONFIG, f"Missing required key: {key}"

    def test_default_config_attack_type(self):
        """Test default attack_type is 'flipattack'."""
        assert DEFAULT_FLIPATTACK_CONFIG["attack_type"] == "flipattack"

    def test_default_flipattack_params(self):
        """Test default flipattack_params values."""
        fa_params = DEFAULT_FLIPATTACK_CONFIG["flipattack_params"]
        assert fa_params["flip_mode"] == "FCS"
        assert fa_params["cot"] is False
        assert fa_params["lang_gpt"] is False
        assert fa_params["few_shot"] is False

    def test_default_judges_configured(self):
        """Test default judges list has at least one judge."""
        judges = DEFAULT_FLIPATTACK_CONFIG["judges"]
        assert isinstance(judges, list)
        assert len(judges) >= 1
        assert "identifier" in judges[0]
        assert "type" in judges[0]

    def test_default_config_deep_copy_independence(self):
        """Test that deep copying the default config creates independent copy."""
        config_copy = copy.deepcopy(DEFAULT_FLIPATTACK_CONFIG)
        config_copy["flipattack_params"]["flip_mode"] = "FWO"

        # Original should not be modified
        assert DEFAULT_FLIPATTACK_CONFIG["flipattack_params"]["flip_mode"] == "FCS"

    def test_default_config_valid_for_flipattack_config(self):
        """Test default config can be loaded into FlipAttackConfig."""
        config = FlipAttackConfig.model_validate(DEFAULT_FLIPATTACK_CONFIG)

        assert config.attack_type == "flipattack"
        assert config.flipattack_params.flip_mode == "FCS"
        assert len(config.judges) >= 1
