# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import unittest
from typing import Any, Dict
from hackagent.router.router import Agent


# A minimal concrete implementation of the abstract Agent class for testing
class ConcreteTestAgent(Agent):
    def __init__(self, id: str, config: Dict[str, Any]):
        super().__init__(id, config)

    def handle_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        # This method needs to be implemented but won't be called in this specific test
        return {"status": "handled", "request_id": request_data.get("id")}


class TestBaseAgent(unittest.TestCase):
    def test_get_identifier(self):
        agent_id = "test_agent_123"
        agent_config = {"key": "value"}
        agent = ConcreteTestAgent(id=agent_id, config=agent_config)
        self.assertEqual(agent.get_identifier(), agent_id)

    def test_init_stores_id_and_config(self):
        agent_id = "config_test_agent"
        agent_config = {"param1": "val1", "param2": 42}
        agent = ConcreteTestAgent(id=agent_id, config=agent_config)
        self.assertEqual(agent.id, agent_id)
        self.assertEqual(agent.config, agent_config)


if __name__ == "__main__":
    unittest.main()
