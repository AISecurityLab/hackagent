import os

import pytest

from hackagent import HackAgent
from hackagent.router.types import AgentTypeEnum

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

DATASET = {
    "preset": "harmbench",
    "limit": 100,
    "shuffle": False,
    "seed": 42,
}
TARGET_MODEL = "anthropic/claude-opus-4.6"
TARGET_ENDPOINT = "https://openrouter.ai/api/v1"

@pytest.mark.e2e
def test_tap():
    openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
    if not openrouter_api_key:
        pytest.skip("OPENROUTER_API_KEY not set")

    agent = HackAgent(
        name=TARGET_MODEL,
        endpoint=TARGET_ENDPOINT,
        agent_type=AgentTypeEnum.OPENAI_SDK,
        adapter_operational_config={
            "name": TARGET_MODEL,
            "api_key": OPENROUTER_API_KEY,
            "endpoint": TARGET_ENDPOINT,
        },
    )

    config = {
        "attack_type": "tap",
        "dataset": DATASET,
        "judge_batch_size": 10,
        "goal_batch_size": 2,
        "goal_batch_workers": 2,
        "max_tokens": 8000,
        "tap_params": {
            "depth": 10,
            "width": 10,
            "branching_factor": 4,
            "n_streams": 3,
        },
    }

    results = agent.hack(attack_config=config)
    print(f"Attack completed: {results}")


test_tap()
