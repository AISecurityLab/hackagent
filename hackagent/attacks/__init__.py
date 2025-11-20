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
Attack module for HackAgent security assessment framework.

This package contains various attack implementations designed to test the security
and robustness of AI agents and language models. The attacks are built on a common
base class and follow established patterns for extensibility and maintainability.

Available attacks:
- AdvPrefix: Adversarial prefix generation attacks using uncensored and target models
- Base attack classes and utilities for implementing new attack types
- Strategy pattern implementations for flexible attack execution

The module integrates with the HackAgent backend for result tracking and reporting.
"""

from .strategies import AdvPrefix, AttackStrategy

__all__ = [
    "AttackStrategy",
    "AdvPrefix",
]
