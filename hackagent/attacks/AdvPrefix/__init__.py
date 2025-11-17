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
AdvPrefix attack implementation package.

This package contains the modular components for implementing adversarial prefix
generation attacks. The attack pipeline consists of multiple stages including
prefix generation, evaluation, filtering, and selection.

Modules:
- config: Configuration settings and default parameters
- generate: Prefix generation using uncensored models
- compute_ce: Cross-entropy computation and scoring
- completions: Target model completion generation
- evaluation: Attack success evaluation and scoring
- preprocessing: Input preprocessing and validation
- aggregation: Result aggregation across multiple runs
- selection: Final prefix selection based on success metrics
- utils: Utility functions and helpers
"""

import warnings

# Suppress pandas FutureWarnings specifically for groupby operations
# This addresses warnings from preprocessing operations in the AdvPrefix pipeline
warnings.filterwarnings(
    "ignore", category=FutureWarning, message=".*include_groups.*", module="pandas.*"
)
