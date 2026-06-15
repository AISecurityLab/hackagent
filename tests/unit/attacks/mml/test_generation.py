# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Unit tests for MML generation module (generation.py).

Tests the generation helper functions and execute() with mocked AgentRouter.
"""

import logging
from unittest.mock import MagicMock

import pytest

from hackagent.attacks.techniques.mml.generation import (
    _build_multimodal_messages,
    _build_text_prompt,
    _random_shuffle_words,
    execute,
)


# ============================================================================
# _random_shuffle_words TESTS
# ============================================================================


class TestRandomShuffleWords:
    """Test the word shuffling helper."""

    def test_returns_list(self):
        """Test that it returns a list."""
        result = _random_shuffle_words("hello world foo")
        assert isinstance(result, list)

    def test_contains_all_original_words(self):
        """Test shuffled list contains all original words."""
        sentence = "the quick brown fox"
        result = _random_shuffle_words(sentence)
        assert sorted(result) == sorted(sentence.split())

    def test_same_length(self):
        """Test shuffled list has same length."""
        sentence = "one two three four five"
        result = _random_shuffle_words(sentence)
        assert len(result) == 5

    def test_single_word(self):
        """Test with single word."""
        result = _random_shuffle_words("hello")
        assert result == ["hello"]

    def test_empty_string(self):
        """Test with empty string."""
        result = _random_shuffle_words("")
        assert result == [""] or result == []


# ============================================================================
# _build_text_prompt TESTS
# ============================================================================


class TestBuildTextPrompt:
    """Test text prompt construction."""

    def test_word_replacement_game(self):
        """Test building prompt for word_replacement + game."""
        encoding_result = {
            "scrambled_words": ["hello", "world"],
            "replacement_dict": {"apple": "hello"},
        }
        prompt = _build_text_prompt("word_replacement", "game", encoding_result)
        assert "apple" in prompt
        assert "hello" in prompt

    def test_word_replacement_control(self):
        """Test building prompt for word_replacement + control."""
        encoding_result = {
            "scrambled_words": ["foo", "bar"],
            "replacement_dict": {"cherry": "foo"},
        }
        prompt = _build_text_prompt("word_replacement", "control", encoding_result)
        assert "cherry" in prompt
        assert "foo" in prompt

    def test_mirror_game(self):
        """Test building prompt for mirror + game."""
        encoding_result = {"scrambled_words": ["test", "words"]}
        prompt = _build_text_prompt("mirror", "game", encoding_result)
        assert "test" in prompt
        assert "mirror" in prompt.lower()

    def test_rotate_game(self):
        """Test building prompt for rotate + game."""
        encoding_result = {"scrambled_words": ["alpha", "beta"]}
        prompt = _build_text_prompt("rotate", "game", encoding_result)
        assert "alpha" in prompt

    def test_base64_game(self):
        """Test building prompt for base64 + game."""
        encoding_result = {"scrambled_words": ["one", "two"]}
        prompt = _build_text_prompt("base64", "game", encoding_result)
        assert "one" in prompt
        assert "base64" in prompt.lower()

    def test_invalid_mode_raises(self):
        """Test that invalid mode raises ValueError."""
        with pytest.raises(ValueError):
            _build_text_prompt("invalid", "game", {})


# ============================================================================
# _build_multimodal_messages TESTS
# ============================================================================


class TestBuildMultimodalMessages:
    """Test multimodal message construction."""

    def test_returns_list_of_one_message(self):
        """Test output is a list with one message."""
        msgs = _build_multimodal_messages("hello", "data:image/png;base64,abc")
        assert isinstance(msgs, list)
        assert len(msgs) == 1

    def test_message_role_is_user(self):
        """Test message role is 'user'."""
        msgs = _build_multimodal_messages("text", "url")
        assert msgs[0]["role"] == "user"

    def test_content_has_text_and_image(self):
        """Test content has both text and image_url parts."""
        msgs = _build_multimodal_messages("my prompt", "data:image/png;base64,xyz")
        content = msgs[0]["content"]
        assert len(content) == 2

        text_part = content[0]
        image_part = content[1]

        assert text_part["type"] == "text"
        assert text_part["text"] == "my prompt"
        assert image_part["type"] == "image_url"
        assert image_part["image_url"]["url"] == "data:image/png;base64,xyz"

    def test_preserves_exact_text(self):
        """Test that text is not modified."""
        text = "exact text with {special} chars"
        msgs = _build_multimodal_messages(text, "url")
        assert msgs[0]["content"][0]["text"] == text


# ============================================================================
# execute() TESTS
# ============================================================================


class TestGenerationExecute:
    """Test the generation execute function with mocked dependencies."""

    def _make_mock_router(self, response_text="Mocked LLM response"):
        """Create a mock AgentRouter."""
        router = MagicMock()
        router.backend_agent = MagicMock()
        router.backend_agent.id = "test-agent-id"
        router.route_request.return_value = {
            "generated_text": response_text,
            "error_message": None,
        }
        return router

    def _make_config(self, encoding_mode="word_replacement", prompt_style="game"):
        """Create a minimal config for generation."""
        return {
            "mml_params": {
                "encoding_mode": encoding_mode,
                "prompt_style": prompt_style,
                "image_width": 800,
                "image_height": 400,
                "font_size": 24,
                "background_color": "white",
                "text_color": "black",
                "num_replacements": 3,
            },
            "batch_size": 1,
        }

    def test_returns_list(self):
        """Test that execute returns a list."""
        router = self._make_mock_router()
        config = self._make_config()
        logger = logging.getLogger("test")

        results = execute(["test goal"], router, config, logger)
        assert isinstance(results, list)

    def test_result_count_matches_goals(self):
        """Test one result per goal."""
        router = self._make_mock_router()
        config = self._make_config()
        logger = logging.getLogger("test")

        results = execute(["goal1", "goal2"], router, config, logger)
        assert len(results) == 2

    def test_result_contains_goal(self):
        """Test each result contains the original goal."""
        router = self._make_mock_router()
        config = self._make_config()
        logger = logging.getLogger("test")

        results = execute(["my test goal"], router, config, logger)
        assert results[0]["goal"] == "my test goal"

    def test_result_contains_encoding_mode(self):
        """Test each result has encoding_mode field."""
        router = self._make_mock_router()
        config = self._make_config(encoding_mode="mirror")
        logger = logging.getLogger("test")

        results = execute(["test"], router, config, logger)
        assert results[0]["encoding_mode"] == "mirror"

    def test_result_contains_response(self):
        """Test result includes model response."""
        router = self._make_mock_router(response_text="Model said this")
        config = self._make_config()
        logger = logging.getLogger("test")

        results = execute(["test goal"], router, config, logger)
        assert results[0]["response"] == "Model said this"

    def test_empty_goals_returns_empty(self):
        """Test that empty goals list returns empty results."""
        router = self._make_mock_router()
        config = self._make_config()
        logger = logging.getLogger("test")

        results = execute([], router, config, logger)
        assert results == []

    @pytest.mark.parametrize(
        "mode", ["word_replacement", "mirror", "rotate", "base64", "mixed"]
    )
    def test_all_encoding_modes(self, mode):
        """Test generation works with all encoding modes."""
        router = self._make_mock_router()
        config = self._make_config(encoding_mode=mode)
        logger = logging.getLogger("test")

        results = execute(["test goal"], router, config, logger)
        assert len(results) == 1
        assert results[0]["encoding_mode"] == mode

    def test_handles_router_error(self):
        """Test graceful handling when router returns an error."""
        router = MagicMock()
        router.backend_agent = MagicMock()
        router.backend_agent.id = "test-agent-id"
        router.route_request.return_value = {
            "generated_text": None,
            "error_message": "Model unavailable",
        }
        config = self._make_config()
        logger = logging.getLogger("test")

        results = execute(["test"], router, config, logger)
        assert len(results) == 1
        # Should still return a result (may have None response or error field)

    def test_tracker_in_config(self):
        """Test that tracker from config is used without error."""
        router = self._make_mock_router()
        config = self._make_config()
        config["_tracker"] = MagicMock()
        logger = logging.getLogger("test")

        # Should not raise
        results = execute(["test goal"], router, config, logger)
        assert len(results) == 1
