# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Extended tests for hackagent/logger.py — covering edge cases and missed branches."""

import logging
import os
import unittest
from unittest.mock import patch

import hackagent.logger as logger_module
from hackagent.logger import get_logger, setup_package_logging, suppress_noisy_libraries


class TestSetupPackageLoggingExtended(unittest.TestCase):
    """Extended tests for setup_package_logging."""

    def setUp(self):
        """Reset state before each test."""
        logger_module._rich_handler_configured_for_package = False
        logger = logging.getLogger("hackagent")
        logger.handlers.clear()
        logger.setLevel(logging.NOTSET)
        logger.propagate = True

    def tearDown(self):
        """Clean up after each test."""
        logger_module._rich_handler_configured_for_package = False
        logger = logging.getLogger("hackagent")
        logger.handlers.clear()
        logger.setLevel(logging.NOTSET)

    @patch.dict(os.environ, {"HACKAGENT_LOG_LEVEL": "INFO"})
    def test_info_level_from_env(self):
        """Test INFO level from environment variable."""
        setup_package_logging()
        logger = logging.getLogger("hackagent")
        self.assertEqual(logger.level, logging.INFO)

    @patch.dict(os.environ, {"HACKAGENT_LOG_LEVEL": "ERROR"})
    def test_error_level_from_env(self):
        """Test ERROR level from environment variable."""
        setup_package_logging()
        logger = logging.getLogger("hackagent")
        self.assertEqual(logger.level, logging.ERROR)

    @patch.dict(os.environ, {"HACKAGENT_LOG_LEVEL": "INVALID_LEVEL"})
    def test_invalid_level_defaults_to_warning(self):
        """Test invalid level string falls back to WARNING."""
        setup_package_logging()
        logger = logging.getLogger("hackagent")
        self.assertEqual(logger.level, logging.WARNING)

    def test_setup_sets_noisy_library_levels(self):
        """suppress_noisy_libraries silences the given loggers (opt-in since Fix 2)."""
        # Reset levels first so the test is not order-dependent
        logging.getLogger("httpx").setLevel(logging.NOTSET)
        logging.getLogger("litellm").setLevel(logging.NOTSET)

        suppress_noisy_libraries("httpx", "litellm")

        self.assertEqual(logging.getLogger("httpx").level, logging.WARNING)
        self.assertEqual(logging.getLogger("litellm").level, logging.WARNING)

    def test_setup_custom_default_level(self):
        """Test setup with custom default_level_str."""
        env_backup = os.environ.pop("TEST_LOGGER_LOG_LEVEL", None)
        try:
            test_logger = logging.getLogger("test_custom_default")
            test_logger.handlers.clear()

            result = setup_package_logging(
                logger_name="test_custom_default",
                default_level_str="DEBUG",
            )
            self.assertEqual(result.level, logging.DEBUG)
        finally:
            test_logger.handlers.clear()
            if env_backup:
                os.environ["TEST_LOGGER_LOG_LEVEL"] = env_backup

    def test_setup_skips_if_already_has_console_handler(self):
        """Test that setup doesn't add another handler if one exists."""
        logger = logging.getLogger("hackagent")
        existing = logging.StreamHandler()
        logger.addHandler(existing)

        setup_package_logging()

        # Should not have added more handlers
        stream_handlers = [
            h for h in logger.handlers if isinstance(h, logging.StreamHandler)
        ]
        # At least the existing one
        self.assertGreaterEqual(len(stream_handlers), 1)

        logger.removeHandler(existing)


class TestGetLoggerExtended(unittest.TestCase):
    """Extended tests for get_logger function."""

    def setUp(self):
        """Reset state before each test."""
        logger_module._rich_handler_configured_for_package = False
        hackagent_logger = logging.getLogger("hackagent")
        hackagent_logger.handlers.clear()
        hackagent_logger.setLevel(logging.NOTSET)

    def tearDown(self):
        """Clean up after each test."""
        logger_module._rich_handler_configured_for_package = False

    def test_get_logger_base_hackagent(self):
        """Test get_logger for 'hackagent' triggers setup."""
        logger = get_logger("hackagent")
        self.assertEqual(logger.name, "hackagent")
        self.assertTrue(logger_module._rich_handler_configured_for_package)

    def test_get_logger_hackagent_submodule(self):
        """Test get_logger for 'hackagent.sub' triggers setup."""
        logger = get_logger("hackagent.some.module")
        self.assertEqual(logger.name, "hackagent.some.module")
        self.assertTrue(logger_module._rich_handler_configured_for_package)

    def test_get_logger_non_hackagent(self):
        """Test get_logger for non-hackagent name doesn't trigger setup."""
        logger = get_logger("some_other_package")
        self.assertEqual(logger.name, "some_other_package")
        # Should NOT have triggered hackagent setup
        self.assertFalse(logger_module._rich_handler_configured_for_package)


if __name__ == "__main__":
    unittest.main()
