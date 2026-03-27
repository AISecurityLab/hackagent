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

ATTACKER_MODEL = "mistralai/mistral-small-3.2-24b-instruct"
ATTACKER_ENDPOINT = "https://openrouter.ai/api/v1"

JUDGE_MODEL = "openai/gpt-4o-mini"
JUDGE_ENDPOINT = "https://openrouter.ai/api/v1"


@pytest.mark.e2e
def test_pair():
    openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
    if not openrouter_api_key:
        pytest.skip("OPENROUTER_API_KEY not set")

    agent = HackAgent(
        name=ATTACKER_MODEL,
        endpoint=TARGET_ENDPOINT,
        agent_type=AgentTypeEnum.OPENAI_SDK,
        adapter_operational_config={
            "name": ATTACKER_MODEL,
            "api_key": OPENROUTER_API_KEY,
            "endpoint": TARGET_ENDPOINT,
        },
    )

    config = {
        "attack_type": "pair",
        "dataset": DATASET,
        "goal_batch_size": 5,
        "goal_batch_workers": 5,
        "max_tokens": 1000,
        "n_iterations": 5,
        "attacker": {
            "identifier": ATTACKER_MODEL,
            "endpoint": ATTACKER_ENDPOINT,
            "agent_type": "OPENAI_SDK",
            "api_key": OPENROUTER_API_KEY,
            "max_tokens": 600,
            "temperature": 1.0,
        },
        "judges": [
            {
                "identifier": JUDGE_MODEL,
                "type": "harmbench",
                "agent_type": AgentTypeEnum.OPENAI_SDK,
                "api_key": openrouter_api_key,
                "endpoint": JUDGE_ENDPOINT,
            },
        ],
    }

    results = agent.hack(attack_config=config)
    print(f"Attack completed: {results}")


test_pair()
