# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

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
