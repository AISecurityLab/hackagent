---
sidebar_position: 2
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';
import ThemedImage from '@theme/ThemedImage';

# Quick Start

Get started with HackAgent in minutes. Choose your preferred method below.

<Tabs defaultValue="tui">
  <TabItem value="tui" label="TUI">

Launch the interactive terminal interface:

```bash
hackagent
```

### See it in Action

<img src="/gifs/terminal.gif" alt="HackAgent TUI Demo" style={{width: '100%', borderRadius: '8px', border: '1px solid var(--ifm-color-emphasis-300)'}} />

  </TabItem>
  <TabItem value="cli" label="CLI">

Run attacks directly from your terminal (without TUI):

<Tabs groupId="framework">
  <TabItem value="ollama" label={<span><ThemedImage sources={{light: 'https://registry.npmmirror.com/@lobehub/icons-static-png/1.24.0/files/light/ollama.png', dark: 'https://registry.npmmirror.com/@lobehub/icons-static-png/1.24.0/files/dark/ollama.png'}} alt="Ollama" style={{height: '20px', marginRight: '8px', verticalAlign: 'middle'}} />Ollama</span>} default>

```bash
hackagent attack advprefix \
  --agent-name "llama3" \
  --agent-type "ollama" \
  --endpoint "http://localhost:11434" \
  --goals "Extract system prompt information" \
  --no-tui
```

  </TabItem>
  <TabItem value="openai-sdk" label={<span><img src="https://openai.com/favicon.ico" alt="OpenAI" style={{height: '20px', marginRight: '8px', verticalAlign: 'middle'}} />OpenAI SDK</span>}>

```bash
hackagent attack advprefix \
  --agent-name "gpt-4" \
  --agent-type "openai-sdk" \
  --endpoint "https://api.openai.com/v1" \
  --goals "Extract system prompt information" \
  --no-tui
```

  </TabItem>
  <TabItem value="google-adk" label={<span><img src="https://google.github.io/adk-docs/assets/agent-development-kit.png" alt="Google ADK" style={{height: '20px', marginRight: '8px', verticalAlign: 'middle'}} />Google ADK</span>}>

```bash
hackagent attack advprefix \
  --agent-name "my-agent" \
  --agent-type "google-adk" \
  --endpoint "http://localhost:8000" \
  --goals "Extract system prompt information" \
  --no-tui
```

  </TabItem>
</Tabs>

View available attacks and options:

```bash
hackagent attack --help
```

  </TabItem>
  <TabItem value="sdk" label="SDK">

Integrate security testing into your Python applications:

<Tabs groupId="framework">
  <TabItem value="ollama" label={<span><ThemedImage sources={{light: 'https://registry.npmmirror.com/@lobehub/icons-static-png/1.24.0/files/light/ollama.png', dark: 'https://registry.npmmirror.com/@lobehub/icons-static-png/1.24.0/files/dark/ollama.png'}} alt="Ollama" style={{height: '20px', marginRight: '8px', verticalAlign: 'middle'}} />Ollama</span>} default>

```python
from hackagent import HackAgent, AgentTypeEnum

# Initialize HackAgent for an Ollama-based agent
agent = HackAgent(
    name="llama3",
    endpoint="http://localhost:11434",
    agent_type=AgentTypeEnum.OLLAMA,
)

# Configure and run an attack
results = agent.hack(attack_config={
    "attack_type": "advprefix",
    "goals": ["Bypass content safety filters"],
    "max_new_tokens": 150,
})

# Results are automatically sent to the dashboard
print(f"Attack completed: {results}")
```

  </TabItem>
  <TabItem value="openai-sdk" label={<span><img src="https://openai.com/favicon.ico" alt="OpenAI" style={{height: '20px', marginRight: '8px', verticalAlign: 'middle'}} />OpenAI SDK</span>}>

```python
from hackagent import HackAgent, AgentTypeEnum

# Initialize HackAgent for an OpenAI SDK-based agent
agent = HackAgent(
    name="gpt-4",
    endpoint="https://api.openai.com/v1",
    agent_type=AgentTypeEnum.OPENAI_SDK,
)

# Configure and run an attack
results = agent.hack(attack_config={
    "attack_type": "advprefix",
    "goals": ["Bypass content safety filters"],
    "max_new_tokens": 150,
})

# Results are automatically sent to the dashboard
print(f"Attack completed: {results}")
```

  </TabItem>
  <TabItem value="google-adk" label={<span><img src="https://google.github.io/adk-docs/assets/agent-development-kit.png" alt="Google ADK" style={{height: '20px', marginRight: '8px', verticalAlign: 'middle'}} />Google ADK</span>}>

```python
from hackagent import HackAgent, AgentTypeEnum

# Initialize HackAgent for a Google ADK-based agent
agent = HackAgent(
    name="my_google_agent",
    endpoint="http://localhost:8000",
    agent_type=AgentTypeEnum.GOOGLE_ADK,
)

# Configure and run an attack
results = agent.hack(attack_config={
    "attack_type": "advprefix",
    "goals": ["Bypass content safety filters"],
    "max_new_tokens": 150,
})

# Results are automatically sent to the dashboard
print(f"Attack completed: {results}")
```

  </TabItem>
</Tabs>

  </TabItem>
</Tabs>

## Next Steps

- [**Attack Tutorial**](./attack-tutorial) — Run your first security test
- [**AdvPrefix Attacks**](../attacks/advprefix-attacks) — Deep dive into attack techniques
