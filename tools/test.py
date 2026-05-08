from hackagent import HackAgent
from hackagent.router.types import AgentTypeEnum

from tools.config import (
    TARGET_MODEL,
    TARGET_ENDPOINT,
    openrouter_api_key,
    ALL_ATTACK_CONFIGS,
)


if __name__ == "__main__":
    for attack_type in ["advprefix"]:
        agent = HackAgent(
            name=TARGET_MODEL,
            endpoint=TARGET_ENDPOINT,
            agent_type=AgentTypeEnum.OLLAMA,
            adapter_operational_config={
                "role": "target",
                "name": TARGET_MODEL,
                "api_key": openrouter_api_key,
                "endpoint": TARGET_ENDPOINT,
                "timeout": 1,
            },
        )
    results = agent.hack(attack_config=ALL_ATTACK_CONFIGS[attack_type]())
    print(f"Attack completed ({attack_type}): {results}")
