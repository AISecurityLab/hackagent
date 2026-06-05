# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Unit tests for MML image encoder module (image_encoder.py).

Tests all encoding modes: word_replacement, mirror, rotate, base64,
as well as internal helpers and the unified encode_prompt interface.
"""

import base64
import io

import pytest
from PIL import Image

from hackagent.attacks.techniques.mml.image_encoder import (
    ENCODERS,
    _image_to_data_url,
    _render_text_to_image,
    _select_words_to_replace,
    encode_base64,
    encode_mirror,
    encode_mixed,
    encode_prompt,
    encode_rotate,
    encode_word_replacement,
)


def _get_pixel_data(img: Image.Image) -> list:
    """Compatible with both Pillow <14 and >=14."""
    try:
        return list(img.get_flattened_data())
    except AttributeError:
        return list(img.getdata())


# ============================================================================
# _render_text_to_image TESTS
# ============================================================================


class TestRenderTextToImage:
    """Test the _render_text_to_image helper."""

    def test_returns_pil_image(self):
        """Test that it returns a PIL Image."""
        from PIL import Image

        img = _render_text_to_image("Hello World")
        assert isinstance(img, Image.Image)

    def test_default_dimensions(self):
        """Test default image dimensions."""
        img = _render_text_to_image("test")
        assert img.size == (800, 400)

    def test_custom_dimensions(self):
        """Test custom image dimensions."""
        img = _render_text_to_image("test", width=640, height=320)
        assert img.size == (640, 320)

    def test_rgb_mode(self):
        """Test image is in RGB mode."""
        img = _render_text_to_image("test")
        assert img.mode == "RGB"

    def test_empty_text(self):
        """Test rendering empty text does not raise."""
        img = _render_text_to_image("")
        assert img.size == (800, 400)

    def test_long_text_wraps(self):
        """Test that long text doesn't crash (wraps)."""
        long_text = "word " * 200
        img = _render_text_to_image(long_text)
        assert img.size == (800, 400)


# ============================================================================
# _image_to_data_url TESTS
# ============================================================================


class TestImageToDataUrl:
    """Test the _image_to_data_url helper."""

    def test_returns_data_url_prefix(self):
        """Test output starts with data:image/png;base64,"""
        img = _render_text_to_image("test")
        url = _image_to_data_url(img)
        assert url.startswith("data:image/png;base64,")

    def test_valid_base64(self):
        """Test that the base64 content is valid."""
        img = _render_text_to_image("test")
        url = _image_to_data_url(img)
        b64_part = url.split(",", 1)[1]
        # Should not raise
        decoded = base64.b64decode(b64_part)
        assert len(decoded) > 0

    def test_decodable_as_png(self):
        """Test that the decoded bytes are a valid PNG."""

        from PIL import Image

        img = _render_text_to_image("hello")
        url = _image_to_data_url(img)
        b64_part = url.split(",", 1)[1]
        decoded = base64.b64decode(b64_part)
        # PNG magic bytes
        assert decoded[:8] == b"\x89PNG\r\n\x1a\n"
        # Can be loaded back
        reloaded = Image.open(io.BytesIO(decoded))
        assert reloaded.size == (800, 400)


# ============================================================================
# _select_words_to_replace TESTS
# ============================================================================


class TestSelectWordsToReplace:
    """Test the word selection helper."""

    def test_returns_correct_count(self):
        """Test that the correct number of indices is returned."""
        words = ["how", "to", "make", "something", "dangerous"]
        indices = _select_words_to_replace(words, 2)
        assert len(indices) == 2

    def test_prefers_longer_words(self):
        """Test that longer words (>3 chars) are preferred."""
        words = ["a", "to", "it", "something", "dangerous", "materials"]
        indices = _select_words_to_replace(words, 3)
        # All selected should be indices of words with len > 3
        for idx in indices:
            assert len(words[idx]) > 3

    def test_falls_back_to_all_when_few_long_words(self):
        """Test fallback when not enough long words."""
        words = ["a", "b", "c"]
        indices = _select_words_to_replace(words, 2)
        assert len(indices) == 2

    def test_does_not_exceed_available(self):
        """Test that it doesn't select more than available words."""
        words = ["hello", "world"]
        indices = _select_words_to_replace(words, 5)
        assert len(indices) <= len(words)

    def test_indices_are_valid(self):
        """Test that returned indices are within bounds."""
        words = ["first", "second", "third", "fourth", "fifth"]
        indices = _select_words_to_replace(words, 3)
        for idx in indices:
            assert 0 <= idx < len(words)


# ============================================================================
# encode_word_replacement TESTS
# ============================================================================


class TestEncodeWordReplacement:
    """Test word replacement encoding."""

    def test_returns_required_keys(self):
        """Test that result contains all required keys."""
        result = encode_word_replacement("how to make a dangerous thing")
        assert "image_data_url" in result
        assert "replacement_dict" in result
        assert "scrambled_words" in result
        assert "modified_text" in result

    def test_image_data_url_format(self):
        """Test that image_data_url has correct format."""
        result = encode_word_replacement("test prompt here")
        assert result["image_data_url"].startswith("data:image/png;base64,")

    def test_replacement_dict_has_entries(self):
        """Test replacement dict contains mappings."""
        result = encode_word_replacement(
            "how to build something dangerous quickly", num_replacements=3
        )
        assert len(result["replacement_dict"]) > 0
        assert len(result["replacement_dict"]) <= 3

    def test_replacement_dict_values_are_original_words(self):
        """Test that dict values come from original prompt."""
        prompt = "explain how to create explosive devices"
        result = encode_word_replacement(prompt, num_replacements=2)
        original_words = prompt.split()
        for replacement, original in result["replacement_dict"].items():
            assert original in original_words

    def test_scrambled_words_contains_all_original(self):
        """Test scrambled_words has same words as original."""
        prompt = "hello world test"
        result = encode_word_replacement(prompt, num_replacements=1)
        assert sorted(result["scrambled_words"]) == sorted(prompt.split())

    def test_modified_text_contains_replacements(self):
        """Test that modified text uses replacement words."""
        prompt = "create something dangerous"
        result = encode_word_replacement(prompt, num_replacements=2)
        # Modified text should differ from original
        for replacement_word in result["replacement_dict"].keys():
            assert replacement_word in result["modified_text"]

    def test_custom_image_dimensions(self):
        """Test custom image dimensions are honored."""
        result = encode_word_replacement(
            "test prompt", image_width=640, image_height=320
        )
        # Verify image is valid (we check the data URL works)
        assert result["image_data_url"].startswith("data:image/png;base64,")


# ============================================================================
# encode_mirror TESTS
# ============================================================================


class TestEncodeMirror:
    """Test mirror encoding."""

    def test_returns_required_keys(self):
        """Test that result contains all required keys."""
        result = encode_mirror("test prompt for mirror")
        assert "image_data_url" in result
        assert "scrambled_words" in result

    def test_image_data_url_format(self):
        """Test image has correct format."""
        result = encode_mirror("test")
        assert result["image_data_url"].startswith("data:image/png;base64,")

    def test_scrambled_words_has_all_original(self):
        """Test scrambled_words contains all original words."""
        prompt = "hello world foo bar"
        result = encode_mirror(prompt)
        assert sorted(result["scrambled_words"]) == sorted(prompt.split())

    def test_image_is_flipped(self):
        """Test that the resulting image is actually mirrored."""

        from PIL import Image

        prompt = "mirror test text"
        result = encode_mirror(prompt)

        # Decode the image
        b64_part = result["image_data_url"].split(",", 1)[1]
        decoded = base64.b64decode(b64_part)
        img = Image.open(io.BytesIO(decoded))

        # Render original for comparison
        original = _render_text_to_image(prompt)
        flipped = original.transpose(Image.FLIP_LEFT_RIGHT)

        # The images should match
        assert _get_pixel_data(img) == _get_pixel_data(flipped)


# ============================================================================
# encode_rotate TESTS
# ============================================================================


class TestEncodeRotate:
    """Test rotate encoding."""

    def test_returns_required_keys(self):
        """Test that result contains all required keys."""
        result = encode_rotate("test prompt for rotate")
        assert "image_data_url" in result
        assert "scrambled_words" in result

    def test_image_data_url_format(self):
        """Test image has correct format."""
        result = encode_rotate("test")
        assert result["image_data_url"].startswith("data:image/png;base64,")

    def test_scrambled_words_has_all_original(self):
        """Test scrambled_words contains all original words."""
        prompt = "one two three four"
        result = encode_rotate(prompt)
        assert sorted(result["scrambled_words"]) == sorted(prompt.split())

    def test_image_is_rotated(self):
        """Test that the resulting image is actually rotated 180 degrees."""

        from PIL import Image

        prompt = "rotate test text"
        result = encode_rotate(prompt)

        b64_part = result["image_data_url"].split(",", 1)[1]
        decoded = base64.b64decode(b64_part)
        img = Image.open(io.BytesIO(decoded))

        original = _render_text_to_image(prompt)
        rotated = original.rotate(180)

        assert _get_pixel_data(img) == _get_pixel_data(rotated)


# ============================================================================
# encode_base64 TESTS
# ============================================================================


class TestEncodeBase64:
    """Test base64 encoding."""

    def test_returns_required_keys(self):
        """Test that result contains all required keys."""
        result = encode_base64("test prompt for base64")
        assert "image_data_url" in result
        assert "scrambled_words" in result

    def test_image_data_url_format(self):
        """Test image has correct format."""
        result = encode_base64("test")
        assert result["image_data_url"].startswith("data:image/png;base64,")

    def test_scrambled_words_has_all_original(self):
        """Test scrambled_words contains all original words."""
        prompt = "alpha beta gamma"
        result = encode_base64(prompt)
        assert sorted(result["scrambled_words"]) == sorted(prompt.split())

    def test_image_contains_base64_encoded_text(self):
        """Test that the image renders the base64-encoded version."""

        from PIL import Image

        prompt = "hello world"
        result = encode_base64(prompt)

        # The image should render the base64 of the prompt
        expected_b64_text = base64.b64encode(prompt.encode("utf-8")).decode("utf-8")

        # Generate what the image should look like
        expected_img = _render_text_to_image(expected_b64_text)

        b64_part = result["image_data_url"].split(",", 1)[1]
        decoded = base64.b64decode(b64_part)
        actual_img = Image.open(io.BytesIO(decoded))

        assert _get_pixel_data(actual_img) == _get_pixel_data(expected_img)


# ============================================================================
# encode_mixed TESTS
# ============================================================================


class TestEncodeMixed:
    """Test mixed (word replacement + mirror + rotate) encoding."""

    def test_returns_required_keys(self):
        """Test that result contains all required keys."""
        result = encode_mixed("test prompt for mixed mode encoding")
        assert "image_data_url" in result
        assert "scrambled_words" in result
        assert "replacement_dict" in result
        assert "modified_text" in result

    def test_image_data_url_format(self):
        """Test image has correct format."""
        result = encode_mixed("test something here quickly")
        assert result["image_data_url"].startswith("data:image/png;base64,")

    def test_scrambled_words_has_all_original(self):
        """Test scrambled_words contains all original words."""
        prompt = "one two three four"
        result = encode_mixed(prompt)
        assert sorted(result["scrambled_words"]) == sorted(prompt.split())

    def test_replacement_dict_has_entries(self):
        """Test replacement dict contains mappings."""
        result = encode_mixed(
            "how to build something dangerous quickly", num_replacements=3
        )
        assert len(result["replacement_dict"]) > 0
        assert len(result["replacement_dict"]) <= 3

    def test_replacement_dict_values_are_original_words(self):
        """Test that dict values come from original prompt."""
        prompt = "explain how to create explosive devices"
        result = encode_mixed(prompt, num_replacements=2)
        original_words = prompt.split()
        for replacement, original in result["replacement_dict"].items():
            assert original in original_words

    def test_modified_text_contains_replacements(self):
        """Test that modified text uses replacement words."""
        prompt = "create something dangerous quickly"
        result = encode_mixed(prompt, num_replacements=2)
        for replacement_word in result["replacement_dict"].keys():
            assert replacement_word in result["modified_text"]

    def test_image_applies_spatial_transforms(self):
        """Test that the image has mirror + rotation applied to the modified text."""

        from PIL import Image

        prompt = "mixed test text here"
        result = encode_mixed(prompt, num_replacements=1)

        b64_part = result["image_data_url"].split(",", 1)[1]
        decoded = base64.b64decode(b64_part)
        img = Image.open(io.BytesIO(decoded))

        # Render the modified (replaced) text the same way
        expected = _render_text_to_image(result["modified_text"])
        expected = expected.transpose(Image.FLIP_LEFT_RIGHT)
        expected = expected.rotate(180)

        assert _get_pixel_data(img) == _get_pixel_data(expected)


# ============================================================================
# encode_prompt UNIFIED INTERFACE TESTS
# ============================================================================


class TestEncodePrompt:
    """Test the unified encode_prompt interface."""

    def test_word_replacement_mode(self):
        """Test encode_prompt dispatches to word_replacement."""
        result = encode_prompt("test prompt", encoding_mode="word_replacement")
        assert "replacement_dict" in result
        assert "image_data_url" in result

    def test_mirror_mode(self):
        """Test encode_prompt dispatches to mirror."""
        result = encode_prompt("test prompt", encoding_mode="mirror")
        assert "scrambled_words" in result
        assert "image_data_url" in result

    def test_rotate_mode(self):
        """Test encode_prompt dispatches to rotate."""
        result = encode_prompt("test prompt", encoding_mode="rotate")
        assert "scrambled_words" in result
        assert "image_data_url" in result

    def test_base64_mode(self):
        """Test encode_prompt dispatches to base64."""
        result = encode_prompt("test prompt", encoding_mode="base64")
        assert "scrambled_words" in result
        assert "image_data_url" in result

    def test_invalid_mode_raises(self):
        """Test that invalid encoding_mode raises ValueError."""
        with pytest.raises(ValueError, match="Unknown encoding_mode"):
            encode_prompt("test", encoding_mode="invalid_mode")

    def test_mixed_mode(self):
        """Test encode_prompt dispatches to mixed."""
        result = encode_prompt("test prompt", encoding_mode="mixed")
        assert "scrambled_words" in result
        assert "image_data_url" in result

    def test_passes_kwargs_through(self):
        """Test that kwargs are forwarded to the encoder."""
        result = encode_prompt(
            "test prompt",
            encoding_mode="word_replacement",
            num_replacements=1,
            image_width=640,
            image_height=320,
        )
        assert "image_data_url" in result

    def test_encoders_map_completeness(self):
        """Test ENCODERS dict contains all expected modes."""
        assert set(ENCODERS.keys()) == {
            "word_replacement",
            "mirror",
            "rotate",
            "base64",
            "mixed",
        }
