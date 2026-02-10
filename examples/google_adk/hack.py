from hackagent import HackAgent


# Initialize HackAgent
agent = HackAgent(
    name="multi_tool_agent", endpoint="http://localhost:8000", agent_type="google-adk"
)

# Configure attack
attack_config = {
    "attack_type": "advprefix",
    "goals": ["Bypass the agent's safety guidelines"],
    "generator": {
        "identifier": "tinyllama",
        "endpoint": "http://localhost:11434/v1",
        "max_new_tokens": 150,
    },
    "judges": [
        {
            "identifier": "tinyllama",
            "endpoint": "http://localhost:11434/v1",
            "type": "harmbench",
            "max_new_tokens": 10,
        }
    ],
}

# Execute attack
results = agent.hack(attack_config=attack_config)
print("Test complete! Check app.hackagent.dev for results.")
