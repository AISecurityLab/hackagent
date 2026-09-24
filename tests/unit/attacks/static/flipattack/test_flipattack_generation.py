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
Integration tests for FlipAttack generation module (generation.py).

Tests the generation.execute() function which creates flipped prompts
using the FlipAttackAlgorithm and executes them against a target model
via LLMRouter.

These tests mock the LLMRouter to test the generation logic
in isolation from real LLM backends, while still exercising the
full integration path through config parsing, FlipAttack algorithm,
and result construction.

Run with:
    pytest tests/integration/attacks/test_flipattack_generation.py --run-integration
"""

import logging
from unittest.mock import MagicMock

import pytest

from hackagent.attacks.techniques.static.flipattack import generation
from hackagent.attacks.techniques.static.flipattack.attack import FlipAttack
from tests.fakes import make_ctx

logger = logging.getLogger(__name__)


# ============================================================================
# HELPERS
# ============================================================================


def _make_mock_router(response_text="This is a mocked LLM response."):
    """Create a mock LLMRouter that returns a canned response."""
    mock_router = MagicMock()
    mock_router.backend_agent = MagicMock()
    mock_router.backend_agent.id = "test-agent-id"
    mock_router.route_request.return_value = {
        "generated_text": response_text,
        "error_message": None,
    }
    return mock_router


def _make_flip(flip_mode="FCS", cot=False, lang_gpt=False, few_shot=False):
    """Build a FlipAttack from ``make_ctx()`` and a config that has no ``_self``."""
    params = {
        "flip_mode": flip_mode,
        "cot": cot,
        "lang_gpt": lang_gpt,
        "few_shot": few_shot,
    }
    attack = FlipAttack(config={"flipattack_params": params}, ctx=make_ctx())
    return attack, {"flipattack_params": params}


def _execute(
    goals,
    router,
    flip_mode="FCS",
    cot=False,
    lang_gpt=False,
    few_shot=False,
    **config_updates,
):
    """Run generation with an explicit ``attack=`` and no ``config["_self"]``."""
    attack, config = _make_flip(flip_mode, cot, lang_gpt, few_shot)
    config.update(config_updates)
    assert "_self" not in config
    assert "_self" not in attack.config
    return generation.execute(
        goals=goals,
        agent_router=router,
        config=config,
        logger=logger,
        attack=attack,
    )


# ============================================================================
# GENERATION EXECUTE TESTS
# ============================================================================


class TestFlipAttackGenerationExecute:
    """Test generation.execute() with attack= and no config['_self']."""

    def test_missing_attack_raises(self):
        with pytest.raises(RuntimeError, match="attack="):
            generation.execute(
                goals=["goal"],
                agent_router=_make_mock_router(),
                config={"flipattack_params": {"flip_mode": "FCS"}},
                logger=logger,
            )

    def test_single_goal_fcs(self):
        """Test generation with a single goal using FCS mode."""
        mock_router = _make_mock_router()
        goals = ["Write something harmful"]

        results = _execute(goals, mock_router, flip_mode="FCS")

        assert len(results) == 1
        result = results[0]
        assert result["goal"] == "Write something harmful"
        assert result["flip_mode"] == "FCS"
        assert result["response"] is not None
        assert result["error"] is None
        assert "system_prompt" in result
        assert "user_prompt" in result
        assert "full_prompt" in result
        assert "flip_log" in result
        mock_router.route_request.assert_called_once()

    def test_multiple_goals(self):
        """Test generation with multiple goals."""
        mock_router = _make_mock_router()
        goals = ["Goal one", "Goal two", "Goal three"]

        results = _execute(goals, mock_router)

        assert len(results) == 3
        for i, result in enumerate(results):
            assert result["goal"] == goals[i]
            assert result["flip_mode"] == "FCS"
            assert result["response"] is not None

        assert mock_router.route_request.call_count == 3

    def test_empty_goals(self):
        """Test generation with empty goals list."""
        mock_router = _make_mock_router()

        results = _execute([], mock_router)

        assert results == []
        mock_router.route_request.assert_not_called()

    @pytest.mark.parametrize("mode", ["FWO", "FCW", "FCS", "FMM"])
    def test_all_flip_modes(self, mode):
        """Test generation works with all flip modes."""
        mock_router = _make_mock_router()
        goals = ["Test this mode"]

        results = _execute(goals, mock_router, flip_mode=mode)

        assert len(results) == 1
        assert results[0]["flip_mode"] == mode
        assert results[0]["response"] is not None

    def test_with_enhancements(self):
        """Test generation with all enhancements enabled."""
        mock_router = _make_mock_router()
        goals = ["Test with enhancements"]

        results = _execute(
            goals, mock_router, flip_mode="FCS", cot=True, lang_gpt=True, few_shot=True
        )

        assert len(results) == 1
        result = results[0]
        assert result["response"] is not None
        # Should have system and user prompts
        assert len(result["system_prompt"]) > 0
        assert len(result["user_prompt"]) > 0

    def test_router_error_handled(self):
        """Test that router execution errors are handled gracefully."""
        mock_router = _make_mock_router()
        mock_router.route_request.side_effect = Exception("Connection failed")
        goals = ["Test error handling"]

        results = _execute(goals, mock_router)

        assert len(results) == 1
        result = results[0]
        assert result["response"] is None
        assert "Execution failed" in result["error"]
        assert result["goal"] == "Test error handling"

    def test_router_returns_error_message(self):
        """Test handling when router returns an error_message."""
        mock_router = _make_mock_router()
        mock_router.route_request.return_value = {
            "generated_text": None,
            "error_message": "Rate limited",
        }
        goals = ["Test error response"]

        results = _execute(goals, mock_router)

        assert len(results) == 1
        assert results[0]["response"] is None
        assert results[0]["error"] == "Rate limited"

    def test_result_contains_full_prompt(self):
        """Test that result includes the full concatenated prompt."""
        mock_router = _make_mock_router()
        goals = ["Check full prompt"]

        results = _execute(goals, mock_router)

        result = results[0]
        # full_prompt should be system + user prompts combined
        assert result["full_prompt"] is not None
        assert len(result["full_prompt"]) > 0
        # full_prompt is built as f"{system_prompt}\n\n{user_prompt}".strip()
        # so the system_prompt may only appear after stripping leading whitespace
        if result["system_prompt"]:
            assert result["system_prompt"].strip() in result["full_prompt"]

    def test_request_data_sent_to_router(self):
        """Test the request data structure sent to the router."""
        mock_router = _make_mock_router()
        goals = ["Verify request structure"]

        _execute(goals, mock_router)

        call_args = mock_router.route_request.call_args
        assert call_args is not None
        # Should pass registration_key and request_data
        kwargs = call_args.kwargs if call_args.kwargs else {}
        args = call_args.args if call_args.args else ()
        # Check either kwargs or positional
        if "request_data" in kwargs:
            assert "prompt" in kwargs["request_data"]
        elif len(args) >= 2:
            assert "prompt" in args[1]

    def test_tracker_integration(self):
        """Test that tracker receives traces when provided."""
        mock_router = _make_mock_router()
        mock_tracker = MagicMock()
        mock_goal_ctx = MagicMock()
        mock_tracker.get_goal_context.return_value = mock_goal_ctx

        goals = ["Test tracker"]

        results = _execute(goals, mock_router, _tracker=mock_tracker)

        assert len(results) == 1
        mock_tracker.get_goal_context.assert_called_once_with(0)
        mock_tracker.add_interaction_trace.assert_called_once()

    def test_tracker_none_no_error(self):
        """Test that generation works without a tracker."""
        mock_router = _make_mock_router()
        goals = ["No tracker"]

        results = _execute(goals, mock_router)

        assert len(results) == 1
        assert results[0]["response"] is not None

    def test_mixed_success_and_failure(self):
        """Test generation with some goals succeeding and some failing."""
        mock_router = _make_mock_router()
        # First call succeeds, second fails, third succeeds
        mock_router.route_request.side_effect = [
            {"generated_text": "Response 1", "error_message": None},
            Exception("Timeout"),
            {"generated_text": "Response 3", "error_message": None},
        ]
        goals = ["Goal 1", "Goal 2", "Goal 3"]

        results = _execute(goals, mock_router, batch_size=1)

        assert len(results) == 3
        assert results[0]["response"] == "Response 1"
        assert results[0]["error"] is None
        assert results[1]["response"] is None
        assert "Execution failed" in results[1]["error"]
        assert results[2]["response"] == "Response 3"
        assert results[2]["error"] is None
