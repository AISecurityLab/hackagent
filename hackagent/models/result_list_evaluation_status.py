# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from enum import Enum


class ResultListEvaluationStatus(str, Enum):
    ERROR_AGENT_RESPONSE = "ERROR_AGENT_RESPONSE"
    ERROR_TEST_FRAMEWORK = "ERROR_TEST_FRAMEWORK"
    FAILED_CRITERIA = "FAILED_CRITERIA"
    FAILED_JAILBREAK = "FAILED_JAILBREAK"
    NOT_EVALUATED = "NOT_EVALUATED"
    PASSED_CRITERIA = "PASSED_CRITERIA"
    SUCCESSFUL_JAILBREAK = "SUCCESSFUL_JAILBREAK"

    def __str__(self) -> str:
        return str(self.value)
