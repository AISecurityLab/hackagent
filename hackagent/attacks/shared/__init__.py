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
Shared components for attacks.

This module contains reusable components used across different
objectives and techniques.
"""

from .progress import create_progress_bar
from .response_utils import extract_response_content
from .router_factory import create_router
from .tui import with_tui_logging

__all__ = [
    "create_progress_bar",
    "create_router",
    "extract_response_content",
    "with_tui_logging",
]
