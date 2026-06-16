# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Unit tests for MML config module (config.py).

Tests DEFAULT_MML_CONFIG structure and Pydantic config models.
"""

import pytest

from hackagent.attacks.techniques.mml.config import (
    DEFAULT_MML_CONFIG,
    MMLConfig,
    MMLParams,
)


# ============================================================================
# DEFAULT_MML_CONFIG TESTS
# ============================================================================


class TestDefaultMMLConfig:
    """Test DEFAULT_MML_CONFIG dict structure."""

    def test_has_attack_type(self):
        """Test config has attack_type key."""
        assert DEFAULT_MML_CONFIG["attack_type"] == "mml"

    def test_has_mml_params(self):
        """Test config has mml_params key."""
        assert "mml_params" in DEFAULT_MML_CONFIG
        assert isinstance(DEFAULT_MML_CONFIG["mml_params"], dict)

    def test_default_encoding_mode(self):
        """Test default encoding_mode is word_replacement."""
        assert DEFAULT_MML_CONFIG["mml_params"]["encoding_mode"] == "word_replacement"

    def test_default_prompt_style(self):
        """Test default prompt_style is game."""
        assert DEFAULT_MML_CONFIG["mml_params"]["prompt_style"] == "game"

    def test_default_image_dimensions(self):
        """Test default image dimensions."""
        params = DEFAULT_MML_CONFIG["mml_params"]
        assert params["image_width"] == 800
        assert params["image_height"] == 400

    def test_default_font_size(self):
        """Test default font size."""
        assert DEFAULT_MML_CONFIG["mml_params"]["font_size"] == 24

    def test_default_colors(self):
        """Test default colors."""
        params = DEFAULT_MML_CONFIG["mml_params"]
        assert params["background_color"] == "white"
        assert params["text_color"] == "black"

    def test_default_num_replacements(self):
        """Test default num_replacements."""
        assert DEFAULT_MML_CONFIG["mml_params"]["num_replacements"] == 3


# ============================================================================
# MMLParams PYDANTIC MODEL TESTS
# ============================================================================


class TestMMLParams:
    """Test MMLParams Pydantic model."""

    def test_default_values(self):
        """Test default parameter values."""
        params = MMLParams()
        assert params.encoding_mode == "word_replacement"
        assert params.image_width == 800
        assert params.image_height == 400
        assert params.font_size == 24
        assert params.background_color == "white"
        assert params.text_color == "black"
        assert params.num_replacements == 3
        assert params.prompt_style == "game"

    def test_valid_encoding_modes(self):
        """Test all valid encoding modes are accepted."""
        for mode in ["word_replacement", "mirror", "rotate", "base64"]:
            params = MMLParams(encoding_mode=mode)
            assert params.encoding_mode == mode

    def test_invalid_encoding_mode_rejected(self):
        """Test invalid encoding mode is rejected."""
        with pytest.raises(Exception):  # Pydantic ValidationError
            MMLParams(encoding_mode="invalid")

    def test_valid_prompt_styles(self):
        """Test all valid prompt styles are accepted."""
        for style in ["game", "control"]:
            params = MMLParams(prompt_style=style)
            assert params.prompt_style == style

    def test_invalid_prompt_style_rejected(self):
        """Test invalid prompt style is rejected."""
        with pytest.raises(Exception):
            MMLParams(prompt_style="invalid")

    def test_image_width_minimum(self):
        """Test image_width minimum constraint (ge=100)."""
        with pytest.raises(Exception):
            MMLParams(image_width=50)

    def test_image_height_minimum(self):
        """Test image_height minimum constraint (ge=100)."""
        with pytest.raises(Exception):
            MMLParams(image_height=50)

    def test_font_size_minimum(self):
        """Test font_size minimum constraint (ge=8)."""
        with pytest.raises(Exception):
            MMLParams(font_size=2)

    def test_num_replacements_minimum(self):
        """Test num_replacements minimum constraint (ge=1)."""
        with pytest.raises(Exception):
            MMLParams(num_replacements=0)

    def test_custom_values(self):
        """Test setting custom values."""
        params = MMLParams(
            encoding_mode="base64",
            image_width=1024,
            image_height=512,
            font_size=32,
            background_color="black",
            text_color="white",
            num_replacements=5,
            prompt_style="control",
        )
        assert params.encoding_mode == "base64"
        assert params.image_width == 1024
        assert params.image_height == 512
        assert params.font_size == 32
        assert params.background_color == "black"
        assert params.text_color == "white"
        assert params.num_replacements == 5
        assert params.prompt_style == "control"


# ============================================================================
# MMLConfig PYDANTIC MODEL TESTS
# ============================================================================


class TestMMLConfig:
    """Test MMLConfig Pydantic model."""

    def test_default_attack_type(self):
        """Test default attack_type is 'mml'."""
        config = MMLConfig()
        assert config.attack_type == "mml"

    def test_model_dump(self):
        """Test model_dump returns a dict."""
        config = MMLConfig()
        dumped = config.model_dump()
        assert isinstance(dumped, dict)
        assert dumped["attack_type"] == "mml"
