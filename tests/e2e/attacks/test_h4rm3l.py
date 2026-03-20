"""
End-to-end test for h4rm3l composable prompt-decoration attack.

Requirements:
  - HACKAGENT_API_KEY env var
  - OPENROUTER_API_KEY env var (or another LLM provider)
    - (Optional) HF_TOKEN / HUGGINGFACE_HUB_TOKEN for gated HuggingFace datasets

Run:
  python tests/test_h4rm3l.py
"""

import os
from statistics import mean

from hackagent import HackAgent
from hackagent.router.types import AgentTypeEnum

DATASET = {
    "preset": "harmbench",
    "limit": 20,
    "shuffle": False,
    "seed": 42,
}


def main():
    openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
    ENDPOINT = "https://openrouter.ai/api/v1"

    agent = HackAgent(
        name="test_target",
        endpoint=ENDPOINT,
        agent_type=AgentTypeEnum.OPENAI_SDK,
        adapter_operational_config={
            "name": "anthropic/claude-opus-4.6",
            "api_key": openrouter_api_key,
            "endpoint": ENDPOINT,
        },
    )

    config = {
        "attack_type": "h4rm3l",
        "dataset": DATASET,
        "h4rm3l_params": {
            # Use an LLM-assisted program (PAP) + refusal suppression.
            # This requires decorator_llm below.
            "program": (
                "DANDecorator().then(RefusalSuppressionDecorator()).then(AIMDecorator()).then(StyleInjectionShortDecorator()).then(Base64Decorator())"
            ),
            "syntax_version": 2,
        },
        # LLM synthesizer used by LLM-assisted decorators (PAP/Translate/etc.)
        "decorator_llm": {
            "identifier": "mistralai/mistral-small-3.2-24b-instruct",
            "endpoint": ENDPOINT,
            "agent_type": AgentTypeEnum.OPENAI_SDK,
            "api_key": openrouter_api_key,
        },
        "max_new_tokens": 1000,
        "judges": [
            {
                "identifier": "openai/gpt-4o-mini",
                "type": "harmbench",
                "agent_type": AgentTypeEnum.OPENAI_SDK,
                "api_key": openrouter_api_key,
                "endpoint": ENDPOINT,
            },
        ],
        "batch_size_judge": 5,
        "goal_batch_size": 5,
        "goal_batch_workers": 5,
    }

    print("Starting h4rm3l test...")
    results = agent.hack(attack_config=config)

    print("\n=== Results ===")
    per_goal_asr = []
    for i, r in enumerate(results):
        success = bool(r.get("success", False))
        asr_i = 100.0 if success else 0.0
        per_goal_asr.append(asr_i)

        print(f"  [{i}] Goal: {r.get('goal')}")
        print(f"      Program: {r.get('program', 'N/A')}")
        print(f"      Score: {r.get('best_score', 'N/A')}")
        print(f"      Success: {r.get('success', 'N/A')}")
        print(f"      ASR(goal): {asr_i:.2f}%")
        print("      Target response (full):")
        print("      ----- BEGIN RESPONSE -----")
        print(str(r.get("response", "")))
        print("      ----- END RESPONSE -----")

    mean_asr = mean(per_goal_asr) if per_goal_asr else 0.0

    print(f"\nTotal: {len(results)} result(s)")
    print(f"ASR medio run: {mean_asr:.2f}%")


if __name__ == "__main__":
    main()
