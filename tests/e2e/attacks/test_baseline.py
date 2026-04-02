import os

import pytest

from hackagent import HackAgent
from hackagent.router.types import AgentTypeEnum

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

DATASET = {
    "preset": "harmbench",
    "limit": 200,
    "shuffle": False,
    "seed": 42,
}
TARGET_MODEL = "Gemma-3-27B-it"
TARGET_ENDPOINT = "http://localhost:12000/v1"
JUDGE_MODEL = "Abel-24-HarmClassifier"
JUDGE_ENDPOINT = "http://localhost:12002/v1"


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
        "goal_batch_size": 1,
        "goal_batch_workers": 1,
        "batch_size_judge": 1,
        "batch_size": 1,
        "judges": [
            {
                "identifier": JUDGE_MODEL,
                "type": "harmbench_variant",
                "endpoint": JUDGE_ENDPOINT,
                "agent_type": AgentTypeEnum.OPENAI_SDK,
                "api_key": OPENROUTER_API_KEY,
            }
        ],
    }

    results = agent.hack(attack_config=config)
    print(f"Attack completed: {results}")


test_baseline()
