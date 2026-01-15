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

"""Tests for the errors module."""

import unittest

from hackagent.errors import (
    UnexpectedStatus,
    HackAgentError,
    ApiError,
    UnexpectedStatusError,
)


class TestUnexpectedStatus(unittest.TestCase):
    """Test UnexpectedStatus exception."""

    def test_basic_creation(self):
        """Test basic exception creation."""
        exc = UnexpectedStatus(status_code=500, content=b"Server Error")

        self.assertEqual(exc.status_code, 500)
        self.assertEqual(exc.content, b"Server Error")

    def test_message_format(self):
        """Test exception message format."""
        exc = UnexpectedStatus(status_code=404, content=b"Not Found")

        message = str(exc)
        self.assertIn("404", message)
        self.assertIn("Not Found", message)

    def test_content_decode_error_handling(self):
        """Test that invalid UTF-8 content is handled gracefully."""
        # Invalid UTF-8 bytes
        invalid_content = b"\xff\xfe Invalid bytes"
        exc = UnexpectedStatus(status_code=500, content=invalid_content)

        # Should not raise
        message = str(exc)
        self.assertIn("500", message)

    def test_empty_content(self):
        """Test with empty content."""
        exc = UnexpectedStatus(status_code=204, content=b"")

        self.assertEqual(exc.status_code, 204)
        self.assertEqual(exc.content, b"")

    def test_is_exception(self):
        """Test that it's a proper Exception subclass."""
        exc = UnexpectedStatus(status_code=500, content=b"Error")
        self.assertIsInstance(exc, Exception)


class TestHackAgentError(unittest.TestCase):
    """Test HackAgentError base exception."""

    def test_basic_creation(self):
        """Test basic exception creation."""
        exc = HackAgentError("Something went wrong")

        self.assertEqual(str(exc), "Something went wrong")

    def test_is_exception(self):
        """Test that it's a proper Exception subclass."""
        exc = HackAgentError("Error")
        self.assertIsInstance(exc, Exception)


class TestApiError(unittest.TestCase):
    """Test ApiError exception."""

    def test_basic_creation(self):
        """Test basic exception creation."""
        exc = ApiError("API failed")

        self.assertEqual(exc.message, "API failed")
        self.assertIsNone(exc.status_code)
        self.assertIsNone(exc.response)

    def test_with_status_code(self):
        """Test creation with status code."""
        exc = ApiError("API failed", status_code=500)

        self.assertEqual(exc.status_code, 500)

    def test_with_response(self):
        """Test creation with response data."""
        response_data = {"error": "details", "code": "ERR001"}
        exc = ApiError("API failed", response=response_data)

        self.assertEqual(exc.response, response_data)

    def test_full_creation(self):
        """Test creation with all parameters."""
        response_data = {"error": "Internal Server Error"}
        exc = ApiError("API failed", status_code=500, response=response_data)

        self.assertEqual(exc.message, "API failed")
        self.assertEqual(exc.status_code, 500)
        self.assertEqual(exc.response, response_data)

    def test_inherits_from_hackagent_error(self):
        """Test that ApiError inherits from HackAgentError."""
        exc = ApiError("Error")
        self.assertIsInstance(exc, HackAgentError)

    def test_message_as_string(self):
        """Test that message is accessible via str()."""
        exc = ApiError("Custom error message")
        self.assertEqual(str(exc), "Custom error message")


class TestUnexpectedStatusErrorAlias(unittest.TestCase):
    """Test UnexpectedStatusError backward compatibility alias."""

    def test_alias_is_same_class(self):
        """Test that the alias points to the same class."""
        self.assertIs(UnexpectedStatusError, UnexpectedStatus)

    def test_can_instantiate_via_alias(self):
        """Test that the alias can be used to create instances."""
        exc = UnexpectedStatusError(status_code=500, content=b"Error")

        self.assertIsInstance(exc, UnexpectedStatus)
        self.assertEqual(exc.status_code, 500)


if __name__ == "__main__":
    unittest.main()
