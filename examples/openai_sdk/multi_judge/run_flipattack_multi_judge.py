"""
HackAgent multi-judge FlipAttack run against IBM Granite on OpenRouter.



Run:
  export OPENROUTER_API_KEY=...
  python examples/openai_sdk/ibm_multi_judge/run_flipattack_multi_judge.py
"""

import os

from hackagent import HackAgent
from hackagent.attacks.evaluator.metrics import generate_summary_report
from hackagent.router.types import AgentTypeEnum

HACKAGENT_API_KEY = os.getenv("HACKAGENT_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

TARGET_MODEL = "ibm-granite/granite-4.1-8b"
TARGET_ENDPOINT = "https://openrouter.ai/api/v1"

JUDGE_MODEL = "openai/gpt-4o"
JUDGE_ENDPOINT = "https://openrouter.ai/api/v1"

DATASET = {
    "preset": "harmbench",
    "limit": 20,
    "shuffle": False,
    "seed": 0,
}


def main() -> None:
    if not OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY is required")

    agent = HackAgent(
        name=TARGET_MODEL,
        endpoint=TARGET_ENDPOINT,
        agent_type=AgentTypeEnum.OPENAI_SDK,
        api_key=HACKAGENT_API_KEY,
        adapter_operational_config={
            "name": TARGET_MODEL,
            "api_key": OPENROUTER_API_KEY,
            "endpoint": TARGET_ENDPOINT,
        },
    )

    config = {
        "attack_type": "flipattack",
        "dataset": DATASET,
        "max_tokens": 400,
        "flipattack_params": {
            "flip_mode": "FCS",
            "judge": JUDGE_MODEL,
            "cot": True,
            "lang_gpt": True,
            "few_shot": True,
        },
        "goal_batch_size": 20,
        "goal_batch_workers": 20,
        "judges": [
            {
                "identifier": JUDGE_MODEL,
                "type": "harmbench_variant",
                "agent_type": AgentTypeEnum.OPENAI_SDK,
                "api_key": OPENROUTER_API_KEY,
                "endpoint": JUDGE_ENDPOINT,
            },
            {
                "identifier": JUDGE_MODEL,
                "type": "harmbench",
                "agent_type": AgentTypeEnum.OPENAI_SDK,
                "api_key": OPENROUTER_API_KEY,
                "endpoint": JUDGE_ENDPOINT,
            },
            {
                "identifier": JUDGE_MODEL,
                "type": "jailbreakbench",
                "agent_type": AgentTypeEnum.OPENAI_SDK,
                "api_key": OPENROUTER_API_KEY,
                "endpoint": JUDGE_ENDPOINT,
            },
        ],
        "batch_size_judge": 20,
        "batch_size": 20,
    }

    print("Starting HackAgent FlipAttack multi-judge test...")
    results = agent.hack(attack_config=config)

    rows = results if isinstance(results, list) else []
    summary = generate_summary_report(rows)

    print("\n=== Multi-Judge Summary ===")
    print(f"Total results: {len(rows)}")
    print(f"Majority Vote ASR: {summary.get('majority_vote_asr', 0.0) * 100:.2f}%")
    print(f"Fleiss' kappa: {summary.get('fleiss_kappa', 0.0):.4f}")

    strictness = summary.get("per_judge_strictness", {})
    print("\nPer-judge strictness:")
    for judge_key in sorted(k for k in strictness.keys() if k != "bias_gap"):
        print(f"  {judge_key}: {strictness[judge_key]:.4f}")


if __name__ == "__main__":
    main()
