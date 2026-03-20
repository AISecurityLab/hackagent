import os

import pytest

from hackagent import HackAgent
from hackagent.router.types import AgentTypeEnum

OPENROUTER_ENDPOINT = "https://openrouter.ai/api/v1"
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

DATASET = {
    "preset": "harmbench",
    "limit": 20,
    "shuffle": False,
    "seed": 42,
}
TARGET_MODEL = "anthropic/claude-opus-4.6"
TARGET_ENDPOINT = OPENROUTER_ENDPOINT

ATTACKER_MODEL = "qwen3.5-27b"
ATTACKER_ENDPOINT = "https://somerset-fragrance-wedding-guests.trycloudflare.com/v1"

JUDGE_MODEL = "Abel-24/HarmClassifier"
JUDGE_ENDPOINT = "https://priced-law-nonprofit-eddie.trycloudflare.com/v1"


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
        "goal_batch_size": 10,
        "goal_batch_workers": 10,
        "max_new_tokens": 400,
        "tap_params": {
            "depth": 4,
            "width": 2,
            "branching_factor": 3,
            "n_streams": 3,
        },
        "max_new_tokens_eval": 20,
        "attacker": {
            "identifier": "deepseek/deepseek-v3.2",
            "agent_type": AgentTypeEnum.OPENAI_SDK,
            "api_key": OPENROUTER_API_KEY,
            "endpoint": OPENROUTER_ENDPOINT,
            "max_new_tokens": 4000,
        },
        "judge": {
            "identifier": "deepseek/deepseek-v3.2",
            "type": "harmbench_variant",
            "agent_type": AgentTypeEnum.OPENAI_SDK,
            "api_key": OPENROUTER_API_KEY,
            "endpoint": OPENROUTER_ENDPOINT,
        },
    }

    results = agent.hack(attack_config=config)
    print(f"Attack completed: {results}")


test_tap()
