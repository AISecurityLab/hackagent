# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Root pytest configuration for the hackagent test suite.

This file registers command-line options that need to be available
before pytest collects tests from subdirectories.
"""

import pytest

pytest_plugins = ["tests.support.campaigns"]


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

    parser.addoption(
        "--run-live",
        action="store_true",
        default=False,
        help="Run tests against real model/backend services",
    )
    parser.addoption(
        "--fail-on-skip",
        action="store_true",
        default=False,
        help="Fail if a required test lane skips any test",
    )


def pytest_collection_modifyitems(config, items):
    """Opt in to services explicitly; offline integrations always run."""
    services = {
        "ollama": "--run-ollama",
        "openai_sdk": "--run-openai",
        "google_adk": "--run-google-adk",
        "litellm": "--run-litellm",
    }
    for item in items:
        if item.get_closest_marker("live") is not None:
            if not config.getoption("--run-live"):
                item.add_marker(pytest.mark.skip(reason="requires --run-live"))
            continue
        for marker, option in services.items():
            if item.get_closest_marker(marker) is not None:
                if not (
                    config.getoption("--run-integration") or config.getoption(option)
                ):
                    item.add_marker(
                        pytest.mark.skip(
                            reason=f"requires {option} or --run-integration"
                        )
                    )
                break


def pytest_sessionfinish(session, exitstatus):
    if not session.config.getoption("--fail-on-skip"):
        return
    reporter = session.config.pluginmanager.get_plugin("terminalreporter")
    if reporter is not None and reporter.stats.get("skipped"):
        reporter.write_sep("!", "Required test lane skipped tests")
        session.exitstatus = pytest.ExitCode.TESTS_FAILED
