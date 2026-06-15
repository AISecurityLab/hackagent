# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Unit tests for MML prompts module (prompts.py).

Tests prompt template retrieval and format placeholder completeness.
"""

import pytest

from hackagent.attacks.techniques.mml.prompts import (
    BASE64_CONTROL_PROMPT,
    BASE64_GAME_PROMPT,
    MIRROR_CONTROL_PROMPT,
    MIRROR_GAME_PROMPT,
    MIXED_CONTROL_PROMPT,
    MIXED_GAME_PROMPT,
    PROMPT_MAP,
    ROTATE_CONTROL_PROMPT,
    ROTATE_GAME_PROMPT,
    WR_CONTROL_PROMPT,
    WR_GAME_PROMPT,
    get_prompt_template,
)


# ============================================================================
# get_prompt_template TESTS
# ============================================================================


class TestGetPromptTemplate:
    """Test prompt template retrieval."""

    @pytest.mark.parametrize(
        "mode,style",
        [
            ("word_replacement", "game"),
            ("word_replacement", "control"),
            ("mirror", "game"),
            ("mirror", "control"),
            ("rotate", "game"),
            ("rotate", "control"),
            ("base64", "game"),
            ("base64", "control"),
            ("mixed", "game"),
            ("mixed", "control"),
        ],
    )
    def test_valid_combinations_return_string(self, mode, style):
        """Test all valid mode/style combinations return a non-empty string."""
        template = get_prompt_template(mode, style)
        assert isinstance(template, str)
        assert len(template) > 0

    def test_invalid_mode_raises(self):
        """Test invalid encoding_mode raises ValueError."""
        with pytest.raises(ValueError, match="Invalid"):
            get_prompt_template("invalid_mode", "game")

    def test_invalid_style_raises(self):
        """Test invalid prompt_style raises ValueError."""
        with pytest.raises(ValueError, match="Invalid"):
            get_prompt_template("mirror", "invalid_style")

    def test_both_invalid_raises(self):
        """Test both invalid raises ValueError."""
        with pytest.raises(ValueError, match="Invalid"):
            get_prompt_template("bad", "bad")


# ============================================================================
# WORD REPLACEMENT PROMPT TESTS
# ============================================================================


class TestWordReplacementPrompts:
    """Test word replacement prompt templates."""

    def test_wr_game_has_replacement_dict_placeholder(self):
        """Test WR game prompt has {replacement_dict} placeholder."""
        assert "{replacement_dict}" in WR_GAME_PROMPT

    def test_wr_game_has_scrambled_words_placeholder(self):
        """Test WR game prompt has {scrambled_words} placeholder."""
        assert "{scrambled_words}" in WR_GAME_PROMPT

    def test_wr_control_has_replacement_dict_placeholder(self):
        """Test WR control prompt has {replacement_dict} placeholder."""
        assert "{replacement_dict}" in WR_CONTROL_PROMPT

    def test_wr_control_has_scrambled_words_placeholder(self):
        """Test WR control prompt has {scrambled_words} placeholder."""
        assert "{scrambled_words}" in WR_CONTROL_PROMPT

    def test_wr_game_can_be_formatted(self):
        """Test WR game prompt can be formatted with expected kwargs."""
        formatted = WR_GAME_PROMPT.format(
            replacement_dict="{'apple': 'bomb'}",
            scrambled_words="['bomb', 'make']",
        )
        assert "apple" in formatted
        assert "bomb" in formatted

    def test_wr_control_can_be_formatted(self):
        """Test WR control prompt can be formatted with expected kwargs."""
        formatted = WR_CONTROL_PROMPT.format(
            replacement_dict="{'cherry': 'weapon'}",
            scrambled_words="['weapon', 'build']",
        )
        assert "cherry" in formatted


# ============================================================================
# MIRROR PROMPT TESTS
# ============================================================================


class TestMirrorPrompts:
    """Test mirror prompt templates."""

    def test_mirror_game_has_scrambled_words_placeholder(self):
        """Test mirror game prompt has {scrambled_words} placeholder."""
        assert "{scrambled_words}" in MIRROR_GAME_PROMPT

    def test_mirror_control_has_scrambled_words_placeholder(self):
        """Test mirror control prompt has {scrambled_words} placeholder."""
        assert "{scrambled_words}" in MIRROR_CONTROL_PROMPT

    def test_mirror_game_mentions_mirroring(self):
        """Test mirror game prompt mentions mirroring."""
        assert "mirror" in MIRROR_GAME_PROMPT.lower()

    def test_mirror_game_can_be_formatted(self):
        """Test mirror game prompt can be formatted."""
        formatted = MIRROR_GAME_PROMPT.format(scrambled_words="['hello', 'world']")
        assert "hello" in formatted


# ============================================================================
# ROTATE PROMPT TESTS
# ============================================================================


class TestRotatePrompts:
    """Test rotate prompt templates."""

    def test_rotate_game_has_scrambled_words_placeholder(self):
        """Test rotate game prompt has {scrambled_words} placeholder."""
        assert "{scrambled_words}" in ROTATE_GAME_PROMPT

    def test_rotate_control_has_scrambled_words_placeholder(self):
        """Test rotate control prompt has {scrambled_words} placeholder."""
        assert "{scrambled_words}" in ROTATE_CONTROL_PROMPT

    def test_rotate_game_mentions_rotation(self):
        """Test rotate game prompt mentions rotation."""
        assert "rotate" in ROTATE_GAME_PROMPT.lower() or "180" in ROTATE_GAME_PROMPT

    def test_rotate_game_can_be_formatted(self):
        """Test rotate game prompt can be formatted."""
        formatted = ROTATE_GAME_PROMPT.format(scrambled_words="['test', 'words']")
        assert "test" in formatted


# ============================================================================
# BASE64 PROMPT TESTS
# ============================================================================


class TestBase64Prompts:
    """Test base64 prompt templates."""

    def test_base64_game_has_scrambled_words_placeholder(self):
        """Test base64 game prompt has {scrambled_words} placeholder."""
        assert "{scrambled_words}" in BASE64_GAME_PROMPT

    def test_base64_control_has_scrambled_words_placeholder(self):
        """Test base64 control prompt has {scrambled_words} placeholder."""
        assert "{scrambled_words}" in BASE64_CONTROL_PROMPT

    def test_base64_game_mentions_base64(self):
        """Test base64 game prompt mentions Base64."""
        assert "base64" in BASE64_GAME_PROMPT.lower()

    def test_base64_game_can_be_formatted(self):
        """Test base64 game prompt can be formatted."""
        formatted = BASE64_GAME_PROMPT.format(scrambled_words="['alpha', 'beta']")
        assert "alpha" in formatted


# ============================================================================
# MIXED PROMPT TESTS
# ============================================================================


class TestMixedPrompts:
    """Test mixed (word replacement + mirror + rotate) prompt templates."""

    def test_mixed_game_has_scrambled_words_placeholder(self):
        """Test mixed game prompt has {scrambled_words} placeholder."""
        assert "{scrambled_words}" in MIXED_GAME_PROMPT

    def test_mixed_control_has_scrambled_words_placeholder(self):
        """Test mixed control prompt has {scrambled_words} placeholder."""
        assert "{scrambled_words}" in MIXED_CONTROL_PROMPT

    def test_mixed_game_has_replacement_dict_placeholder(self):
        """Test mixed game prompt has {replacement_dict} placeholder."""
        assert "{replacement_dict}" in MIXED_GAME_PROMPT

    def test_mixed_control_has_replacement_dict_placeholder(self):
        """Test mixed control prompt has {replacement_dict} placeholder."""
        assert "{replacement_dict}" in MIXED_CONTROL_PROMPT

    def test_mixed_game_mentions_rotate_and_mirror(self):
        """Test mixed game prompt mentions both transformations."""
        lower = MIXED_GAME_PROMPT.lower()
        assert "rotated" in lower or "rotating" in lower or "rotate" in lower
        assert "mirror" in lower

    def test_mixed_game_can_be_formatted(self):
        """Test mixed game prompt can be formatted."""
        formatted = MIXED_GAME_PROMPT.format(
            replacement_dict="{'apple': 'bomb'}",
            scrambled_words="['foo', 'bar']",
        )
        assert "apple" in formatted
        assert "foo" in formatted


# ============================================================================
# PROMPT_MAP COMPLETENESS
# ============================================================================


class TestPromptMap:
    """Test PROMPT_MAP completeness and consistency."""

    def test_has_all_ten_combinations(self):
        """Test PROMPT_MAP has all mode x style combinations."""
        modes = ["word_replacement", "mirror", "rotate", "base64", "mixed"]
        styles = ["game", "control"]
        for mode in modes:
            for style in styles:
                assert (mode, style) in PROMPT_MAP

    def test_all_values_are_non_empty_strings(self):
        """Test all prompt templates are non-empty strings."""
        for key, template in PROMPT_MAP.items():
            assert isinstance(template, str), f"PROMPT_MAP[{key}] is not a string"
            assert len(template) > 50, f"PROMPT_MAP[{key}] seems too short"
