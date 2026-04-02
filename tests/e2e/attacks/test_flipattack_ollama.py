from hackagent import HackAgent
from hackagent.router.types import AgentTypeEnum
import os

ENDPOINT_OLLAMA = "http://localhost:11434"

# Goals targeting the specific data exfiltration risk
DATASET = {
    "preset": "harmbench",
    "limit": 1,
    "shuffle": False,
    "seed": 42,
}

agent = HackAgent(
    name="openai/gpt-4o-mini",
    endpoint="https://openrouter.ai/api/v1",
    agent_type=AgentTypeEnum.OPENAI_SDK,
    adapter_operational_config={
        "name": "openai/gpt-4o-mini",
        "api_key": os.getenv("OPENROUTER_API_KEY"),
        "endpoint": "https://openrouter.ai/api/v1",
    },
)

config = {
    "attack_type": "flipattack",
    "dataset": DATASET,
    "max_tokens": 200,
    "flipattack_params": {
        "flip_mode": "FCS",
        "judge": "gemma3:4b",
        "cot": True,
        "lang_gpt": True,
        "fewshot_examples": 5,
    },
    "category_classifier": {
        "identifier": "gemma3:4b",
        "agent_type": AgentTypeEnum.OLLAMA,
        "endpoint": ENDPOINT_OLLAMA,
        "api_key": None,
        "max_tokens": 20,
        "temperature": 0.0,
    },
    "goal_batch_size": 1,
    "goal_batch_workers": 1,
    "judges": [
        {
            "identifier": "gemma3:4b",
            "type": "harmbench_variant",
            "agent_type": AgentTypeEnum.OLLAMA,
            "endpoint": ENDPOINT_OLLAMA,
        },
        {
            "identifier": "gemma3:4b",
            "type": "harmbench",
            "agent_type": AgentTypeEnum.OLLAMA,
            "endpoint": ENDPOINT_OLLAMA,
        },
    ],
    "batch_size_judge": 1,
    "batch_size": 1,
}

# IMPORTANT: local Ollama must be running and model must be available.
results = agent.hack(attack_config=config)
print(f"Attack completed: {results}")
