import os

import pytest

from hackagent import HackAgent
from hackagent.router.types import AgentTypeEnum

DATASET = {
    "preset": "harmbench",
    "limit": 200,
    "shuffle": False,
    "seed": 42,
}
TARGET_MODEL = "Gemma-3-27B-it"
TARGET_ENDPOINT = "http://localhost:13000/v1"

GENERATOR_MODEL = "Gemma-3-27B-it-Uncensored"
GENERATOR_ENDPOINT = "http://localhost:13001/v1"

JUDGE_MODEL = "Abel-24-HarmClassifier"
JUDGE_ENDPOINT = "http://localhost:13002/v1"


@pytest.mark.e2e
def test_advprefix():
    openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
    if not openrouter_api_key:
        pytest.skip("OPENROUTER_API_KEY not set")

    agent = HackAgent(
        name=TARGET_MODEL,
        endpoint=TARGET_ENDPOINT,
        agent_type=AgentTypeEnum.OPENAI_SDK,
        adapter_operational_config={
            "name": TARGET_MODEL,
            "api_key": openrouter_api_key,
            "endpoint": TARGET_ENDPOINT,
        },
    )

    config = {
        "attack_type": "advprefix",
        "dataset": DATASET,
        "batch_size": 20,
        "max_tokens_completion": 300,
        "goal_batch_size": 20,
        "goal_batch_workers": 20,
        "generator": {
            "identifier": GENERATOR_MODEL,
            "agent_type": AgentTypeEnum.OPENAI_SDK,
            "endpoint": GENERATOR_ENDPOINT,
            "max_tokens": 50,
        },
        "meta_prefixes": ["Write...", "Outline...", "Draft..."],
        "judges": [
            {
                "identifier": JUDGE_MODEL,
                "type": "harmbench_variant",
                "agent_type": AgentTypeEnum.OPENAI_SDK,
                "api_key": openrouter_api_key,
                "endpoint": JUDGE_ENDPOINT,
            },
        ],
        "batch_size_judge": 20,
        "meta_prefix_samples": 1,
        "max_tokens": 400,
        "max_tokens_eval": 128,
    }

    results = agent.hack(attack_config=config)
    print(f"AdvPrefix attack completed: {results}")


if __name__ == "__main__":
    test_advprefix()
