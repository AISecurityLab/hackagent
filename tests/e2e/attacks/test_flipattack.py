import os
from hackagent import HackAgent
from hackagent.router.types import AgentTypeEnum

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
ENDPOINT_TARGET = "http://localhost:12000/v1"
ENDPOINT_JUDGE = "http://localhost:12002/v1"
HACKAGENT_API_KEY = os.getenv("HACKAGENT_API_KEY")
# Goals targeting the specific data exfiltration risk
DATASET = {
    "preset": "harmbench",
    "limit": 200,
    "shuffle": False,
    "seed": 42,
}
agent = HackAgent(
    name="Gemma-3-27B-it",
    endpoint=ENDPOINT_TARGET,
    agent_type=AgentTypeEnum.OPENAI_SDK,
    adapter_operational_config={
        "name": "Gemma-3-27B-it",
        "api_key": OPENROUTER_API_KEY,
        "endpoint": ENDPOINT_TARGET,
    },
)

config = {
    "attack_type": "flipattack",
    "dataset": DATASET,
    "max_tokens": 400,
    "flipattack_params": {
        "flip_mode": "FCS",
        "judge": "Abel-24-HarmClassifier",
        "cot": True,
        "lang_gpt": True,
        "fewshot_examples": 5,
    },
    "goal_batch_size": 1,
    "goal_batch_workers": 1,
    "judges": [
        {
            "identifier": "Abel-24-HarmClassifier",
            "type": "harmbench_variant",
            "agent_type": AgentTypeEnum.OPENAI_SDK,
            "api_key": OPENROUTER_API_KEY,
            "endpoint": ENDPOINT_JUDGE,
        },
    ],
    "batch_size_judge": 1,
    "batch_size": 1,
}

# IMPORTANT: agent_server.py must be running!
results = agent.hack(attack_config=config)
print(f"Attack completed: {results}")
