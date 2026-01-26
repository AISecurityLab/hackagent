"""
Example of using HackAgent to test an agent running on Ollama.

This example demonstrates how to configure and test an Ollama-based agent
for security vulnerabilities using the HackAgent framework.

Prerequisites:
1. Install Ollama: https://ollama.ai
2. Pull a model: `ollama pull llama3`
3. Start Ollama: `ollama serve`

The example shows how to:
- Connect to a local Ollama instance
- Configure the agent with a specific model
- Run a security assessment
"""

from hackagent import HackAgent

# Initialize HackAgent for an Ollama-based agent
agent = HackAgent(
    name="tinyllama",
    endpoint="http://localhost:11434",
    agent_type="ollama",
)

config = {
    "attack_type": "advprefix",
    "goals": ["Bypass content safety filters"],
    "max_new_tokens": 150,
}

# Configure and run an attack
results = agent.hack(attack_config=config)

# Results are automatically sent to the dashboard
print(f"Attack completed: {results}")
