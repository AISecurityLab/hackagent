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
Attack techniques module.

Techniques define HOW we generate attacks. Each technique is a complete
implementation that can target different objectives.

Available techniques:
- advprefix/: Prefix optimization using uncensored models + judges
- baseline/: Baseline prompt injection attacks

Architecture pattern for techniques:
    1. attack.py - Main BaseAttack subclass
    2. config.py - Default configuration + dataclasses
    3. generation.py - Attack generation/execution logic
    4. evaluation.py - Result evaluation logic
    5. [other].py - Additional pipeline stages as needed

Techniques are used by BaseAttack subclasses and wrapped by AttackStrategy.
"""

__all__ = []
