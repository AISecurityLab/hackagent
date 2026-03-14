# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tests for the logger module."""

import logging
import os
import unittest
from unittest.mock import patch

from hackagent.logger import setup_package_logging, get_logger
import hackagent.logger as logger_module


class TestSetupPackageLogging(unittest.TestCase):
    """Test setup_package_logging function."""

    def setUp(self):
        """Reset state before each test."""
        # Reset the global flag
        logger_module._rich_handler_configured_for_package = False
        # Clear any existing handlers
        logger = logging.getLogger("hackagent")
        logger.handlers.clear()
        logger.setLevel(logging.NOTSET)
        # Also clear any test loggers
        test_logger = logging.getLogger("test_logger")
        test_logger.handlers.clear()
        test_logger.setLevel(logging.NOTSET)

    def tearDown(self):
        """Clean up loggers after each test."""
        logger_module._rich_handler_configured_for_package = False
        logger = logging.getLogger("hackagent")
        logger.handlers.clear()
        logger.setLevel(logging.NOTSET)

    def test_setup_logging_default_level(self):
        """Test setup with default WARNING level (no env var)."""
        # Make sure env var is not set
        env_backup = os.environ.pop("HACKAGENT_LOG_LEVEL", None)
        try:
            setup_package_logging()
            logger = logging.getLogger("hackagent")
            self.assertEqual(logger.level, logging.WARNING)
        finally:
            if env_backup:
                os.environ["HACKAGENT_LOG_LEVEL"] = env_backup

    @patch.dict(os.environ, {"HACKAGENT_LOG_LEVEL": "DEBUG"})
    def test_setup_logging_env_level(self):
        """Test setup with log level from environment variable."""
        setup_package_logging()

        logger = logging.getLogger("hackagent")
        self.assertEqual(logger.level, logging.DEBUG)

    def test_setup_logging_creates_handler(self):
        """Test that setup creates at least one handler."""
        setup_package_logging()

        logger = logging.getLogger("hackagent")
        self.assertTrue(len(logger.handlers) > 0)

    def test_setup_logging_disables_propagation(self):
        """Test that propagation is disabled."""
        setup_package_logging()

        logger = logging.getLogger("hackagent")
        self.assertFalse(logger.propagate)

    def test_setup_logging_returns_logger(self):
        """Test that setup_package_logging returns the logger."""
        result = setup_package_logging()

        self.assertIsInstance(result, logging.Logger)

    def test_setup_logging_idempotent(self):
        """Test that calling setup multiple times doesn't add duplicate handlers."""
        setup_package_logging()
        handler_count = len(logging.getLogger("hackagent").handlers)

        setup_package_logging()
        new_handler_count = len(logging.getLogger("hackagent").handlers)

        self.assertEqual(handler_count, new_handler_count)

    def test_setup_logging_custom_logger_name(self):
        """Test setup with custom logger name."""
        result = setup_package_logging(logger_name="test_logger")

        self.assertEqual(result.name, "test_logger")


class TestGetLogger(unittest.TestCase):
    """Test get_logger function."""

    def setUp(self):
        """Reset state before each test."""
        logger_module._rich_handler_configured_for_package = False
        logger = logging.getLogger("hackagent")
        logger.handlers.clear()
        logger.setLevel(logging.NOTSET)

    def tearDown(self):
        """Clean up loggers after each test."""
        logger_module._rich_handler_configured_for_package = False

    def test_get_logger_returns_logger(self):
        """Test that get_logger returns a logger instance."""
        logger = get_logger("hackagent.test_module")

        self.assertIsInstance(logger, logging.Logger)

    def test_get_logger_correct_name(self):
        """Test that logger has correct name."""
        logger = get_logger("hackagent.test_module")

        self.assertEqual(logger.name, "hackagent.test_module")

    def test_get_logger_different_names(self):
        """Test that different names return different loggers."""
        logger1 = get_logger("hackagent.module1")
        logger2 = get_logger("hackagent.module2")

        self.assertNotEqual(logger1.name, logger2.name)

    def test_get_logger_same_name_returns_same_logger(self):
        """Test that same name returns same logger instance."""
        logger1 = get_logger("hackagent.same_module")
        logger2 = get_logger("hackagent.same_module")

        self.assertIs(logger1, logger2)

    def test_get_logger_nested_name(self):
        """Test with nested module names."""
        logger = get_logger("hackagent.attacks.base")

        self.assertEqual(logger.name, "hackagent.attacks.base")

    def test_get_logger_non_hackagent(self):
        """Test with non-hackagent logger name."""
        logger = get_logger("other_package")

        self.assertEqual(logger.name, "other_package")


if __name__ == "__main__":
    unittest.main()
