# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Shared test doubles for the attack pipeline's collaborators.

Use these instead of defining per-file dummies. Each fake records what it
was asked to do so tests can assert on calls rather than on internals.
"""

from tests.fakes.context import RecordingEvents, FakeWorkspace, FakeLLMFactory, make_ctx
from tests.fakes.judge import FakeJudge
from tests.fakes.llm import FakeLLM
from tests.fakes.router import FakeRouter
from tests.fakes.settings import isolated_settings
from tests.fakes.storage import in_memory_store
from tests.fakes.tracking import RecordingCoordinator, RecordingStepTracker

__all__ = [
    "FakeJudge",
    "FakeLLM",
    "FakeLLMFactory",
    "FakeRouter",
    "FakeWorkspace",
    "RecordingCoordinator",
    "RecordingEvents",
    "RecordingStepTracker",
    "in_memory_store",
    "isolated_settings",
    "make_ctx",
]
