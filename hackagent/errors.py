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

"""Contains shared errors types that can be raised from API functions"""


class HackAgentError(Exception):
    """Base exception for all HackAgent library specific errors."""

    pass


class ApiError(HackAgentError):
    """Represents an error returned by the API or an issue with API communication."""

    pass


class UnexpectedStatusError(ApiError):
    """Raised when an API response has an unexpected HTTP status code."""

    def __init__(self, status_code: int, content: bytes):
        self.status_code = status_code
        self.content = content
        super().__init__(
            f"Unexpected status code: {status_code}, content: {content.decode('utf-8', errors='replace')}"
        )


UnexpectedStatus = UnexpectedStatusError

__all__ = [
    "HackAgentError",
    "ApiError",
    "UnexpectedStatusError",
    "UnexpectedStatus",
]
