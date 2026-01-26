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

"""Tests for AdvPrefix completion tracking."""

import logging
import unittest
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

from hackagent.attacks.techniques.advprefix import completions


@contextmanager
def _dummy_progress_bar(*args, **kwargs):
    class DummyBar:
        def update(self, *args, **kwargs):
            return None

    yield DummyBar(), "task"


class TestAdvPrefixCompletionTracking(unittest.TestCase):
    """Validate that AdvPrefix completions add per-goal interaction traces."""

    @patch("hackagent.attacks.techniques.advprefix.completions.create_progress_bar")
    def test_execute_adds_goal_traces(self, mock_progress_bar):
        mock_progress_bar.side_effect = _dummy_progress_bar

        agent_router = MagicMock()
        agent_router.backend_agent.id = "agent-123"
        agent_router.backend_agent.agent_type = "OPENAI_SDK"
        agent_router.route_request.return_value = {
            "generated_text": "response text",
            "raw_response_status": 200,
            "raw_response_headers": {},
            "raw_response_body": "body",
            "agent_specific_data": {
                "tool_calls": [
                    {"function": {"name": "tool", "arguments": "{}"}, "id": "1"}
                ]
            },
        }

        goal_tracker = MagicMock()
        goal_tracker.get_goal_context.side_effect = [MagicMock(), MagicMock()]

        config = {
            "surrogate_attack_prompt": "",
            "_goal_tracker": goal_tracker,
            "_run_id": "run-id",
            "_client": MagicMock(),
        }

        input_data = [
            {"goal": "goal-1", "prefix": "prefix-1"},
            {"goal": "goal-2", "prefix": "prefix-2"},
        ]

        completions.execute(
            agent_router=agent_router,
            input_data=input_data,
            config=config,
            logger=logging.getLogger("test"),
        )

        self.assertEqual(goal_tracker.add_interaction_trace.call_count, 2)
        first_call = goal_tracker.add_interaction_trace.call_args_list[0]
        metadata = first_call.kwargs["metadata"]

        self.assertEqual(metadata.get("prefix"), "prefix-1")
        self.assertIn("agent_specific_data", metadata)
        self.assertEqual(metadata.get("raw_response_status"), 200)


if __name__ == "__main__":
    unittest.main()
