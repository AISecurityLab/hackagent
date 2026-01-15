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
Baseline attack technique.

Uses predefined prompt templates combined with harmful goals to attempt
jailbreaks. Simpler than optimization-based approaches like AdvPrefix,
but can be effective for testing basic prompt injection vulnerabilities.

Architecture:
- generation.py: Generate and execute baseline prompts
- evaluation.py: Evaluate responses using objective-based criteria
- attack.py: Main attack class coordinating the pipeline
- config.py: Configuration and defaults
"""

from .attack import BaselineAttack

__all__ = ["BaselineAttack"]
