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
Terminal User Interface (TUI)

Full-featured terminal interface for HackAgent with tabbed navigation,
real-time attack monitoring, and interactive configuration.

Structure:
    - app.py: Main TUI application class
    - base.py: Base widgets and utilities
    - logger.py: TUI logging handler for attack execution logs
    - views/: Tab views (dashboard, agents, attacks, results, config)
    - widgets/: Reusable UI components (log viewer, etc.)
"""

from hackagent.cli.tui.app import HackAgentTUI

__all__ = ["HackAgentTUI"]
