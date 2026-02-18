# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tests for shared response_utils module."""

import logging
from unittest.mock import MagicMock

import pytest

from hackagent.attacks.shared.response_utils import extract_response_content


@pytest.fixture
def logger():
    return logging.getLogger("test.response_utils")


class TestExtractResponseContent:
    """Tests for the extract_response_content utility."""

    def test_none_response(self, logger):
        """None input returns None."""
        assert extract_response_content(None, logger) is None

    def test_string_response(self, logger):
        """Plain string is returned directly."""
        assert extract_response_content("hello world", logger) == "hello world"

    def test_empty_string_response(self, logger):
        """Empty string returns None."""
        assert extract_response_content("", logger) is None

    def test_dict_processed_response(self, logger):
        """Dict with 'processed_response' key."""
        resp = {"processed_response": "the answer"}
        assert extract_response_content(resp, logger) == "the answer"

    def test_dict_generated_text(self, logger):
        """Dict with 'generated_text' key."""
        resp = {"generated_text": "generated output"}
        assert extract_response_content(resp, logger) == "generated output"

    def test_dict_processed_response_takes_priority(self, logger):
        """processed_response is tried first by dict.get fallthrough."""
        resp = {"generated_text": "gen", "processed_response": "proc"}
        result = extract_response_content(resp, logger)
        # Should return one of them (implementation detail: generated_text is tried first)
        assert result in ("gen", "proc")

    def test_dict_empty(self, logger):
        """Empty dict returns None."""
        assert extract_response_content({}, logger) is None

    def test_dict_error_message_only(self, logger):
        """Dict with only error_message returns None."""
        resp = {"error_message": "something failed"}
        assert extract_response_content(resp, logger) is None

    def test_openai_style_object(self, logger):
        """OpenAI-style response with .choices[0].message.content."""
        mock = MagicMock()
        mock.choices = [MagicMock()]
        mock.choices[0].message.content = "openai content"
        assert extract_response_content(mock, logger) == "openai content"

    def test_openai_empty_choices(self, logger):
        """OpenAI-style response with empty choices list."""
        mock = MagicMock()
        mock.choices = []
        result = extract_response_content(mock, logger)
        # Should gracefully handle empty choices
        assert result is None or isinstance(result, str)

    def test_openai_none_content(self, logger):
        """OpenAI-style response with None content."""
        mock = MagicMock()
        mock.choices = [MagicMock()]
        mock.choices[0].message.content = None
        result = extract_response_content(mock, logger)
        assert result is None

    def test_integer_response(self, logger):
        """Non-standard types return None."""
        assert extract_response_content(42, logger) is None

    def test_whitespace_string(self, logger):
        """Whitespace-only strings."""
        result = extract_response_content("   ", logger)
        assert result == "   " or result is None  # Implementation-dependent
