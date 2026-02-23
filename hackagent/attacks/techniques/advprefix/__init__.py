# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
AdvPrefix attack implementation package.

This package contains the modular components for implementing adversarial prefix
generation attacks. The attack pipeline consists of multiple stages including
prefix generation, evaluation, filtering, and selection.

Modules:
- attack: Main AdvPrefixAttack class (BaseAttack implementation)
- config: Configuration settings and default parameters
- generate: Consolidated module containing prefix generation, preprocessing,
  and cross-entropy computation functionality (merged from generate.py,
  preprocessing.py, and compute_ce.py)
- completions: Target model completion generation
- evaluation: Attack success evaluation and scoring
- evaluators: Specialized evaluators (NuancedEvaluator, JailbreakBenchEvaluator, etc.)
- utils: Utility functions and helpers
"""

import warnings

from .attack import AdvPrefixAttack

# Suppress pandas FutureWarnings specifically for groupby operations
# This addresses warnings from preprocessing operations in the AdvPrefix pipeline
warnings.filterwarnings(
    "ignore", category=FutureWarning, message=".*include_groups.*", module="pandas.*"
)

__all__ = ["AdvPrefixAttack"]
