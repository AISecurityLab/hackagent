"""
End-to-end test for Best-of-N (BoN) Jailbreaking attack.

Requirements:
  - HACKAGENT_API_KEY env var
  - OPENROUTER_API_KEY env var (or another LLM provider)

Run:
  python tests/test_bon.py
"""

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
JUDGE_MODEL = "Abel-24-HarmClassifier"
JUDGE_ENDPOINT = "http://localhost:11002/v1"


@pytest.mark.e2e
def test_bon():
    openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
    ENDPOINT = "http://localhost:11000/v1"

    if not openrouter_api_key:
        pytest.skip("OPENROUTER_API_KEY not set")

    agent = HackAgent(
        name="Gemma-3-27B-it",
        endpoint=ENDPOINT,
        agent_type=AgentTypeEnum.OPENAI_SDK,
        adapter_operational_config={
            "name": "Gemma-3-27B-it",
            "api_key": openrouter_api_key,
            "endpoint": ENDPOINT,
        },
    )

    config = {
        "attack_type": "bon",
        "dataset": DATASET,
        "bon_params": {
            "n_steps": 3,
            "num_concurrent_k": 3,
            "sigma": 0.4,
            "word_scrambling": True,
            "random_capitalization": True,
            "ascii_perturbation": True,
        },
        "max_tokens": 600,
        "max_tokens_eval": 100,
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
        "goal_batch_size": 20,
        "goal_batch_workers": 20,
    }

    results = agent.hack(attack_config=config)

    print("\n=== Results ===")
    for i, r in enumerate(results):
        print(f"  [{i}] Goal: {r.get('goal')}")
        print(f"      Score: {r.get('best_score', 'N/A')}")
        print(f"      Success: {r.get('success', 'N/A')}")
        print(
            f"      Step: {r.get('step', 'N/A')}, Candidate: {r.get('candidate', 'N/A')}"
        )
        print(f"      Response: {str(r.get('response', ''))[:120]}...")

    print(f"\nTotal: {len(results)} result(s)")


if __name__ == "__main__":
    test_bon()
