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

ATTACKER_MODEL = "Gemma-3-27B-it-Uncensored"
ATTACKER_ENDPOINT = "http://localhost:12001/v1"

JUDGE_MODEL = "Abel-24-HarmClassifier"
JUDGE_ENDPOINT = "http://localhost:12002/v1"


@pytest.mark.e2e
def test_pair():
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
        "attack_type": "pair",
        "dataset": DATASET,
        "goal_batch_size": 20,
        "goal_batch_workers": 20,
        "max_tokens": 600,
        "n_iterations": 5,
        "attacker": {
            "identifier": ATTACKER_MODEL,
            "endpoint": ATTACKER_ENDPOINT,
            "agent_type": "OPENAI_SDK",
        },
        "scorer": {
            "identifier": ATTACKER_MODEL,
            "agent_type": AgentTypeEnum.OPENAI_SDK,
            "endpoint": ATTACKER_ENDPOINT,
            "max_tokens": 100,
        },
    }

    results = agent.hack(attack_config=config)
    print(f"Attack completed: {results}")


test_pair()
