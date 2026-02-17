# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Root pytest configuration for the hackagent test suite.

This file registers command-line options that need to be available
before pytest collects tests from subdirectories.
"""


def pytest_addoption(parser):
    """Add custom command line options for integration tests.

    These options must be registered at the root conftest.py level
    so they are available before pytest processes subdirectories.
    """
    parser.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="Run integration tests (requires external services)",
    )
    parser.addoption(
        "--run-ollama",
        action="store_true",
        default=False,
        help="Run Ollama integration tests",
    )
    parser.addoption(
        "--run-openai",
        action="store_true",
        default=False,
        help="Run OpenAI SDK integration tests",
    )
    parser.addoption(
        "--run-google-adk",
        action="store_true",
        default=False,
        help="Run Google ADK integration tests",
    )
    parser.addoption(
        "--run-litellm",
        action="store_true",
        default=False,
        help="Run LiteLLM integration tests",
    )
