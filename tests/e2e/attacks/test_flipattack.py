import os
from hackagent import HackAgent
from hackagent.router.types import AgentTypeEnum

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
ENDPOINT_OPENROUTER = "https://openrouter.ai/api/v1"
HACKAGENT_API_KEY = os.getenv("HACKAGENT_API_KEY")
# Goals targeting the specific data exfiltration risk
DATASET = {
    "preset": "harmbench",
    "limit": 5,
    "shuffle": False,
    "seed": 42,
}
agent = HackAgent(
    name="test_target",
    endpoint=ENDPOINT_OPENROUTER,
    agent_type=AgentTypeEnum.OPENAI_SDK,
    adapter_operational_config={
        "name": "google/gemma-3-27b-it",
        "api_key": OPENROUTER_API_KEY,
        "endpoint": ENDPOINT_OPENROUTER,
    },
)

config = {
    "attack_type": "flipattack",
    "dataset": DATASET,
    "max_tokens": 400,
    "flipattack_params": {
        "flip_mode": "FCS",
        "judge": "openai/gpt-4o-mini",
        "cot": True,
        "lang_gpt": True,
        "fewshot_examples": 5,
    },
    "goal_batch_size": 10,
    "goal_batch_workers": 10,
    "judges": [
        {
            "identifier": "openai/gpt-4o-mini",
            "type": "harmbench_variant",
            "agent_type": AgentTypeEnum.OPENAI_SDK,
            "api_key": OPENROUTER_API_KEY,
            "endpoint": ENDPOINT_OPENROUTER,
        },
    ],
    "batch_size_judge": 5,
}

# IMPORTANT: agent_server.py must be running!
results = agent.hack(attack_config=config)
print(f"Attack completed: {results}")
