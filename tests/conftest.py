# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Root pytest configuration for the hackagent test suite.

This file registers command-line options that need to be available
before pytest collects tests from subdirectories.
"""

import sys

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


class _SkipGuard:
    """Fail a required test lane that skipped anything.

    Counts skips from the reports themselves rather than the terminal
    reporter's stats, which are absent under ``-p no:terminal``. A worse
    outcome (failures, an interrupted run, an internal error) keeps its own
    exit status.
    """

    #: Skipped test ids printed when the lane fails; the rest are counted.
    SHOWN = 10

    def __init__(self) -> None:
        # Insertion-ordered and unique: a test can report a skip more than once.
        self.skipped: dict[str, None] = {}

    def _record(self, report) -> None:
        if report.skipped and not hasattr(report, "wasxfail"):
            self.skipped[report.nodeid] = None

    def pytest_runtest_logreport(self, report) -> None:
        self._record(report)

    def pytest_collectreport(self, report) -> None:
        self._record(report)

    def _report(self) -> list[str]:
        skipped = list(self.skipped)
        lines = [f"Required test lane skipped {len(skipped)} test(s):"]
        lines += [f"  {nodeid}" for nodeid in skipped[: self.SHOWN]]
        if len(skipped) > self.SHOWN:
            lines.append(f"  ... and {len(skipped) - self.SHOWN} more")
        return lines

    def pytest_terminal_summary(self, terminalreporter) -> None:
        if not self.skipped:
            return
        title, *details = self._report()
        terminalreporter.write_sep("!", title)
        for line in details:
            terminalreporter.write_line(line)

    def pytest_sessionfinish(self, session) -> None:
        if not self.skipped:
            return
        if session.config.pluginmanager.get_plugin("terminalreporter") is None:
            sys.stderr.write("\n".join(self._report()) + "\n")
        if session.exitstatus == pytest.ExitCode.OK:
            session.exitstatus = pytest.ExitCode.TESTS_FAILED


def pytest_configure(config):
    if config.getoption("--fail-on-skip"):
        config.pluginmanager.register(_SkipGuard(), "fail-on-skip")
