# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Default configuration for the Baseline attack."""

DEFAULT_BASELINE_CONFIG = {
    "max_tokens": 1024,
    "temperature": 0.0,
    "objective": "jailbreak",
    "evaluator_type": "llm_judge",
    "judge_config": None,
    "judges": None,
    "min_response_length": 10,
    "batch_size": 16,
    "output_dir": "./logs/runs",
}
