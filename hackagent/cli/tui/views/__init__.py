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
TUI Views

Tab views/panels for the HackAgent TUI application.
Each view represents a different functional area of the interface.
"""

from hackagent.cli.tui.views.agents import AgentsTab
from hackagent.cli.tui.views.attacks import AttacksTab
from hackagent.cli.tui.views.config import ConfigTab
from hackagent.cli.tui.views.results import ResultsTab

__all__ = ["AgentsTab", "AttacksTab", "ConfigTab", "ResultsTab"]

"""
TUI Tabs Module

Individual tab implementations for the HackAgent TUI.
"""
