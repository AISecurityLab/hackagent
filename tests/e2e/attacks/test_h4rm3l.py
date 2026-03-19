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


def main():
    hackagent_api_key = os.getenv("HACKAGENT_API_KEY")
    openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
    ENDPOINT = "https://openrouter.ai/api/v1"
    dataset_preset = os.getenv("DATASET_PRESET", "harmbench")
    dataset_limit = int(os.getenv("DATASET_LIMIT", "20"))
    dataset_shuffle = os.getenv("DATASET_SHUFFLE", "true").lower() == "true"
    dataset_seed = int(os.getenv("DATASET_SEED", "42"))
    goal_batch_size = int(os.getenv("GOAL_BATCH_SIZE", "10"))
    goal_batch_workers = int(os.getenv("GOAL_BATCH_WORKERS", "10"))
    batch_size_judge = int(os.getenv("BATCH_SIZE_JUDGE", "1"))

    if not hackagent_api_key:
        raise RuntimeError("Set HACKAGENT_API_KEY")
    if not openrouter_api_key:
        raise RuntimeError("Set OPENROUTER_API_KEY")

    agent = HackAgent(
        name="test_h4rm3l_target",
        endpoint=ENDPOINT,
        agent_type=AgentTypeEnum.OPENAI_SDK,
        api_key=hackagent_api_key,
        adapter_operational_config={
            "name": "z-ai/glm-5",
            "api_key": openrouter_api_key,
            "endpoint": ENDPOINT,
        },
    )

    config = {
        "attack_type": "h4rm3l",
        "dataset": {
            "preset": dataset_preset,
            "limit": dataset_limit,
            "shuffle": dataset_shuffle,
            "seed": dataset_seed,
        },
        "h4rm3l_params": {
            # Use an LLM-assisted program (PAP) + refusal suppression.
            # This requires decorator_llm below.
            "program": (
                "DANDecorator().then(Base64Decorator()).then(RefusalSuppressionDecorator()).then(AIMDecorator()).then(StyleInjectionShortDecorator())"
            ),
            "syntax_version": 2,
        },
        # LLM synthesizer used by LLM-assisted decorators (PAP/Translate/etc.)
        "decorator_llm": {
            "identifier": "x-ai/grok-3-mini",
            "endpoint": ENDPOINT,
            "agent_type": AgentTypeEnum.OPENAI_SDK,
            "api_key": openrouter_api_key,
        },
        # Goal batching/workers apply regardless of goal source (direct goals or dataset-loaded goals).
        "goal_batch_size": goal_batch_size,
        "goal_batch_workers": goal_batch_workers,
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
        "batch_size_judge": batch_size_judge,
    }

    print("Starting h4rm3l test...")
    print(
        f"Dataset preset={dataset_preset} limit={dataset_limit} "
        f"shuffle={dataset_shuffle} seed={dataset_seed}"
    )
    print(
        f"Batching: goal_batch_size={goal_batch_size}, "
        f"goal_batch_workers={goal_batch_workers}, batch_size_judge={batch_size_judge}"
    )
    print(f"Program: {config['h4rm3l_params']['program']}")
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
