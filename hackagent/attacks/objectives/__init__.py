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
Attack objectives module.

Objectives define WHAT vulnerabilities we're testing for.
Each objective provides:
- Success/failure patterns
- Evaluation criteria for judges
- Objective-specific context

Note: Objectives are metadata/config, not execution classes.

Available objectives:
- JAILBREAK: Bypass safety guardrails
- HARMFUL_BEHAVIOR: Elicit harmful content
- POLICY_VIOLATION: Cause policy violations with multi-criteria assessment
"""

from .base import ObjectiveConfig
from .jailbreak import JAILBREAK, REFUSAL_PATTERNS as JAILBREAK_REFUSAL_PATTERNS
from .harmful_behavior import HARMFUL_BEHAVIOR
from .policy_violation import POLICY_VIOLATION

# Registry for easy lookup
OBJECTIVES = {
    "jailbreak": JAILBREAK,
    "harmful_behavior": HARMFUL_BEHAVIOR,
    "policy_violation": POLICY_VIOLATION,
}

__all__ = [
    "ObjectiveConfig",
    "JAILBREAK",
    "HARMFUL_BEHAVIOR",
    "POLICY_VIOLATION",
    "OBJECTIVES",
    "JAILBREAK_REFUSAL_PATTERNS",
]
