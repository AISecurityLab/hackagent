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
TARGET_ENDPOINT = "http://localhost:11000/v1"


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
        "judge_batch_size": 20,
        "goal_batch_size": 20,
        "goal_batch_workers": 20,
        "max_tokens": 1000,
        "tap_params": {
            "depth": 3,
            "width": 3,
            "branching_factor": 3,
            "n_streams": 3,
        },
        "judges": [
            {
                "identifier": "Abel-24-HarmClassifier",
                "type": "harmbench_variant",
                "endpoint": "http://localhost:11002/v1",
                "agent_type": AgentTypeEnum.OPENAI_SDK,
                "api_key": OPENROUTER_API_KEY,
            },
        ],
        "judge_temperature": 0.2,
        "attacker": {
            "identifier": "Gemma-3-27B-it-Uncensored",
            "agent_type": AgentTypeEnum.OPENAI_SDK,
            "api_key": OPENROUTER_API_KEY,
            "endpoint": "http://localhost:11001/v1",
            "max_tokens": 1000,
        },
        "on_topic_judge": {
            "identifier": "Gemma-3-27B-it-Uncensored",
            "type": "harmbench_variant",
            "endpoint": "http://localhost:11001/v1",
            "agent_type": AgentTypeEnum.OPENAI_SDK,
            "api_key": OPENROUTER_API_KEY,
            "max_tokens": 100,
        },
    }

    results = agent.hack(attack_config=config)
    print(f"Attack completed: {results}")


test_tap()
