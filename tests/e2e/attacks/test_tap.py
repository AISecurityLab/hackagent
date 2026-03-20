import os

import pytest

from hackagent import HackAgent
from hackagent.router.types import AgentTypeEnum

OPENROUTER_ENDPOINT = "https://openrouter.ai/api/v1"
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

DATASET = {
    "preset": "harmbench",
    "limit": 5,
    "shuffle": False,
    "seed": 42,
}


@pytest.mark.e2e
def test_tap():
    openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
    if not openrouter_api_key:
        pytest.skip("OPENROUTER_API_KEY not set")

    agent = HackAgent(
        name="anthropic/claude-opus-4.6",
        endpoint=OPENROUTER_ENDPOINT,
        agent_type=AgentTypeEnum.OPENAI_SDK,
        adapter_operational_config={
            "name": "anthropic/claude-opus-4.6",
            "api_key": OPENROUTER_API_KEY,
            "endpoint": OPENROUTER_ENDPOINT,
        },
    )

    config = {
        "attack_type": "tap",
        "dataset": DATASET,
        "judge_batch_size": 10,
        "goal_batch_size": 10,
        "goal_batch_workers": 10,
        "max_new_tokens": 800,
        "tap_params": {
            "depth": 2,
            "width": 2,
            "branching_factor": 3,
            "n_streams": 10,
        },
        "attacker": {
            "identifier": "mistralai/mistral-small-3.2-24b-instruct",
            "type": "harmbench",
            "agent_type": AgentTypeEnum.OPENAI_SDK,
            "api_key": openrouter_api_key,
            "endpoint": OPENROUTER_ENDPOINT,
        },
        "judge": {
            "identifier": "anthropic/claude-opus-4.6",
            "type": "harmbench",
            "agent_type": AgentTypeEnum.OPENAI_SDK,
            "api_key": openrouter_api_key,
            "endpoint": OPENROUTER_ENDPOINT,
        },
    }

    results = agent.hack(attack_config=config)
    print(f"Attack completed: {results}")


test_tap()
