import os
from statistics import mean

from hackagent import HackAgent
from hackagent.router.types import AgentTypeEnum


TARGET_MODEL = "ibm-granite/granite-4.1-8b"
TARGET_ENDPOINT = "https://openrouter.ai/api/v1"

ATTACKER_MODEL = "mistralai/mixtral-8x22b-instruct"
ATTACKER_ENDPOINT = "https://openrouter.ai/api/v1"

JUDGE_MODEL = "openai/gpt-4o"
JUDGE_ENDPOINT = "https://openrouter.ai/api/v1"

DATASET = {
    "preset": "harmbench",
    "limit": 200,
    "shuffle": False,
    "seed": 0,
}


def build_target(openrouter_api_key: str) -> HackAgent:
    return HackAgent(
        name=TARGET_MODEL,
        endpoint=TARGET_ENDPOINT,
        agent_type=AgentTypeEnum.OPENAI_SDK,
        adapter_operational_config={
            "name": TARGET_MODEL,
            "api_key": openrouter_api_key,
            "endpoint": TARGET_ENDPOINT,
        },
    )


def summarize_results(results, label: str) -> None:
    per_goal_asr = [100.0 if bool(r.get("success", False)) else 0.0 for r in results]
    mean_asr = mean(per_goal_asr) if per_goal_asr else 0.0
    print(f"\n=== {label} Results ===")
    print(f"Total goals: {len(results)}")
    print(f"Mean ASR: {mean_asr:.2f}%")


def run_h4rm3l() -> list:
    openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
    if not openrouter_api_key:
        raise RuntimeError("OPENROUTER_API_KEY is required")

    target = build_target(openrouter_api_key)

    config = {
        "attack_type": "h4rm3l",
        "dataset": DATASET,
        "h4rm3l_params": {
            "program": "DANDecorator().then(RefusalSuppressionDecorator()).then(AIMDecorator())",
            "syntax_version": 2,
        },
        "decorator_llm": {
            "identifier": ATTACKER_MODEL,
            "endpoint": ATTACKER_ENDPOINT,
            "agent_type": AgentTypeEnum.OPENAI_SDK,
            "api_key": openrouter_api_key,
        },
        "max_tokens": 1000,
        "judges": [
            {
                "identifier": JUDGE_MODEL,
                "type": "harmbench_variant",
                "agent_type": AgentTypeEnum.OPENAI_SDK,
                "api_key": openrouter_api_key,
                "endpoint": JUDGE_ENDPOINT,
            }
        ],
        "category_classifier": {
            "identifier": JUDGE_MODEL,
            "agent_type": AgentTypeEnum.OPENAI_SDK,
            "api_key": openrouter_api_key,
            "endpoint": JUDGE_ENDPOINT,
            "max_tokens": 100,
            "temperature": 0.0,
        },
        "batch_size_judge": 20,
        "goal_batch_size": 20,
        "goal_batch_workers": 20,
    }

    print("Starting h4rm3l on HarmBench...")
    results = target.hack(attack_config=config)
    summarize_results(results, "h4rm3l")
    return results


if __name__ == "__main__":
    run_h4rm3l()
