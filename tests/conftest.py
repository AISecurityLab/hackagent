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
