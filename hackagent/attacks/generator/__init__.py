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
Generator module for attack prompt generation.

This package provides reusable prompt templates and generation
utilities used across different attack techniques.

Modules:
    templates: Attack prompt template library and pattern constants

Usage:
    from hackagent.attacks.generator import (
        AttackTemplates,
        REFUSAL_PATTERNS,
        SUCCESS_PATTERNS,
    )
"""

from hackagent.attacks.generator.templates import (
    REFUSAL_PATTERNS,
    SUCCESS_PATTERNS,
    AttackTemplates,
)

__all__ = [
    "AttackTemplates",
    "REFUSAL_PATTERNS",
    "SUCCESS_PATTERNS",
]
