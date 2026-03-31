import os

import pytest

from hackagent import HackAgent
from hackagent.router.types import AgentTypeEnum

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

DATASET = {
    "preset": "harmbench",
    "limit": 5,
    "shuffle": False,
    "seed": 42,
}
TARGET_MODEL = "google/gemma-3-27b-it"
TARGET_ENDPOINT = "https://openrouter.ai/api/v1"


@pytest.mark.e2e
def test_baseline():
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
        "attack_type": "baseline",
        "dataset": DATASET,
        "max_tokens": 400,
        "goal_batch_size": 5,
        "goal_batch_workers": 5,
        "batch_size_judge": 5,
        "batch_size": 5,
        "judges": [
            {
                "identifier": "openai/gpt-4o-mini",
                "type": "harmbench",
                "endpoint": TARGET_ENDPOINT,
                "agent_type": AgentTypeEnum.OPENAI_SDK,
                "api_key": OPENROUTER_API_KEY,
            }
        ],
    }

    results = agent.hack(attack_config=config)
    print(f"Attack completed: {results}")


test_baseline()
