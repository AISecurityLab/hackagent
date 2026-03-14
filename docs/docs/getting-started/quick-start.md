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

<details style={{background: 'var(--ifm-color-emphasis-100)', border: '1px solid var(--ifm-color-emphasis-200)', borderRadius: '6px', padding: '0.5rem 0.75rem', marginBottom: '0.75rem'}}>
  <summary style={{cursor: 'pointer', fontWeight: 600}}>Prerequisites</summary>

1. Install Ollama: `curl -fsSL https://ollama.com/install.sh | sh`
2. Start server: `ollama serve`
3. Pull model: `ollama pull llama3`
4. Verify: `curl http://localhost:11434/api/tags`
</details>

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

<details style={{background: 'var(--ifm-color-emphasis-100)', border: '1px solid var(--ifm-color-emphasis-200)', borderRadius: '6px', padding: '0.5rem 0.75rem', marginBottom: '0.75rem'}}>
  <summary style={{cursor: 'pointer', fontWeight: 600}}>Prerequisites</summary>

1. Get API key from [platform.openai.com/api-keys](https://platform.openai.com/api-keys)
2. Set env var: `export OPENAI_API_KEY="sk-..."`
3. Verify: `curl https://api.openai.com/v1/models -H "Authorization: Bearer $OPENAI_API_KEY"`
</details>

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

<details style={{background: 'var(--ifm-color-emphasis-100)', border: '1px solid var(--ifm-color-emphasis-200)', borderRadius: '6px', padding: '0.5rem 0.75rem', marginBottom: '0.75rem'}}>
  <summary style={{cursor: 'pointer', fontWeight: 600}}>Prerequisites</summary>

1. Install: `pip install google-adk`
2. Start agent: `cd your_agent && adk web`
3. Verify: `curl http://localhost:8000/list-apps`
</details>

```bash
hackagent attack advprefix \
  --agent-name "my-agent" \
  --agent-type "google-adk" \
  --endpoint "http://localhost:8000" \
  --goals "Extract system prompt information" \
  --no-tui
```

  </TabItem>
  <TabItem value="litellm" label={<span><img src="https://docs.litellm.ai/img/favicon.ico" alt="LiteLLM" style={{height: '20px', marginRight: '8px', verticalAlign: 'middle'}} />LiteLLM</span>}>

<details style={{background: 'var(--ifm-color-emphasis-100)', border: '1px solid var(--ifm-color-emphasis-200)', borderRadius: '6px', padding: '0.5rem 0.75rem', marginBottom: '0.75rem'}}>
  <summary style={{cursor: 'pointer', fontWeight: 600}}>Prerequisites</summary>

1. Install: `pip install litellm[proxy]`
2. Start proxy: `litellm --model gpt-4 --port 4000`
3. Verify: `curl http://localhost:4000/health`
</details>

```bash
hackagent attack advprefix \
  --agent-name "gpt-4" \
  --agent-type "litellm" \
  --endpoint "http://localhost:4000/v1" \
  --goals "Extract system prompt information" \
  --no-tui
```

  </TabItem>
</Tabs>

#### More Frameworks

<Tabs groupId="framework-extra">
  <TabItem value="langchain" label="LangChain" default>

<details style={{background: 'var(--ifm-color-emphasis-100)', border: '1px solid var(--ifm-color-emphasis-200)', borderRadius: '6px', padding: '0.5rem 0.75rem', marginBottom: '0.75rem'}}>
  <summary style={{cursor: 'pointer', fontWeight: 600}}>Prerequisites</summary>

1. Install: `pip install langserve`
2. Start server: `python your_langserve_app.py`
3. Verify: `curl http://localhost:8000/`
</details>

```bash
hackagent attack advprefix \
  --agent-name "my-langchain-agent" \
  --agent-type "langchain" \
  --endpoint "http://localhost:8000" \
  --goals "Extract system prompt information" \
  --no-tui
```

  </TabItem>
  <TabItem value="lmstudio" label="LM Studio">

<details style={{background: 'var(--ifm-color-emphasis-100)', border: '1px solid var(--ifm-color-emphasis-200)', borderRadius: '6px', padding: '0.5rem 0.75rem', marginBottom: '0.75rem'}}>
  <summary style={{cursor: 'pointer', fontWeight: 600}}>Prerequisites</summary>

1. Download from [lmstudio.ai](https://lmstudio.ai)
2. Load a model in LM Studio
3. Start local server: "Local Server" tab → "Start Server"
4. Verify: `curl http://localhost:1234/v1/models`
</details>

```bash
hackagent attack advprefix \
  --agent-name "local-model" \
  --agent-type "openai-sdk" \
  --endpoint "http://localhost:1234/v1" \
  --goals "Extract system prompt information" \
  --no-tui
```

  </TabItem>
  <TabItem value="vllm" label="vLLM">

<details style={{background: 'var(--ifm-color-emphasis-100)', border: '1px solid var(--ifm-color-emphasis-200)', borderRadius: '6px', padding: '0.5rem 0.75rem', marginBottom: '0.75rem'}}>
  <summary style={{cursor: 'pointer', fontWeight: 600}}>Prerequisites</summary>

1. Install: `pip install vllm`
2. Start server: `vllm serve meta-llama/Llama-3-8B-Instruct --port 8000`
3. Verify: `curl http://localhost:8000/v1/models`
</details>

```bash
hackagent attack advprefix \
  --agent-name "my-model" \
  --agent-type "openai-sdk" \
  --endpoint "http://localhost:8000/v1" \
  --goals "Extract system prompt information" \
  --no-tui
```

  </TabItem>
  <TabItem value="custom" label="Custom">

<details style={{background: 'var(--ifm-color-emphasis-100)', border: '1px solid var(--ifm-color-emphasis-200)', borderRadius: '6px', padding: '0.5rem 0.75rem', marginBottom: '0.75rem'}}>
  <summary style={{cursor: 'pointer', fontWeight: 600}}>Prerequisites</summary>

1. Ensure your endpoint exposes `/v1/chat/completions` (OpenAI-compatible)
2. Verify: `curl http://your-endpoint/v1/models`
</details>

```bash
hackagent attack advprefix \
  --agent-name "my-model" \
  --agent-type "openai-sdk" \
  --endpoint "http://your-endpoint/v1" \
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

<details style={{background: 'var(--ifm-color-emphasis-100)', border: '1px solid var(--ifm-color-emphasis-200)', borderRadius: '6px', padding: '0.5rem 0.75rem', marginBottom: '0.75rem'}}>
  <summary style={{cursor: 'pointer', fontWeight: 600}}>Prerequisites</summary>

1. Install Ollama: `curl -fsSL https://ollama.com/install.sh | sh`
2. Start server: `ollama serve`
3. Pull model: `ollama pull llama3`
</details>

```python
from hackagent import HackAgent

# Initialize HackAgent
agent = HackAgent(
  name="llama3",
  endpoint="http://localhost:11434",
  agent_type="ollama",
)
```

  </TabItem>
  <TabItem value="openai-sdk" label={<span><img src="https://openai.com/favicon.ico" alt="OpenAI" style={{height: '20px', marginRight: '8px', verticalAlign: 'middle'}} />OpenAI SDK</span>}>

<details style={{background: 'var(--ifm-color-emphasis-100)', border: '1px solid var(--ifm-color-emphasis-200)', borderRadius: '6px', padding: '0.5rem 0.75rem', marginBottom: '0.75rem'}}>
  <summary style={{cursor: 'pointer', fontWeight: 600}}>Prerequisites</summary>

1. Get API key from [platform.openai.com/api-keys](https://platform.openai.com/api-keys)
2. Set env var: `export OPENAI_API_KEY="sk-..."`
</details>

```python
from hackagent import HackAgent

# Initialize HackAgent
agent = HackAgent(
  name="gpt-4",
  endpoint="https://api.openai.com/v1",
  agent_type="openai-sdk",
)
```

  </TabItem>
  <TabItem value="google-adk" label={<span><img src="https://google.github.io/adk-docs/assets/agent-development-kit.png" alt="Google ADK" style={{height: '20px', marginRight: '8px', verticalAlign: 'middle'}} />Google ADK</span>}>

<details style={{background: 'var(--ifm-color-emphasis-100)', border: '1px solid var(--ifm-color-emphasis-200)', borderRadius: '6px', padding: '0.5rem 0.75rem', marginBottom: '0.75rem'}}>
  <summary style={{cursor: 'pointer', fontWeight: 600}}>Prerequisites</summary>

1. Install: `pip install google-adk`
2. Start agent: `cd your_agent && adk web`
</details>

```python
from hackagent import HackAgent

# Initialize HackAgent
agent = HackAgent(
  name="my_google_agent",
  endpoint="http://localhost:8000",
  agent_type="google-adk",
)
```

  </TabItem>
  <TabItem value="litellm" label={<span><img src="https://docs.litellm.ai/img/favicon.ico" alt="LiteLLM" style={{height: '20px', marginRight: '8px', verticalAlign: 'middle'}} />LiteLLM</span>}>

<details style={{background: 'var(--ifm-color-emphasis-100)', border: '1px solid var(--ifm-color-emphasis-200)', borderRadius: '6px', padding: '0.5rem 0.75rem', marginBottom: '0.75rem'}}>
  <summary style={{cursor: 'pointer', fontWeight: 600}}>Prerequisites</summary>

1. Install: `pip install litellm[proxy]`
2. Start proxy: `litellm --model gpt-4 --port 4000`
</details>

```python
from hackagent import HackAgent

# Initialize HackAgent
agent = HackAgent(
  name="gpt-4",
  endpoint="http://localhost:4000/v1",
  agent_type="litellm",
)
```

  </TabItem>
</Tabs>

```python
# Configure and run an attack
attack_config = {
  "attack_type": "advprefix",
  "goals": ["Bypass content safety filters"]
}

agent.hack(attack_config=attack_config)
```

#### More Frameworks

<Tabs groupId="framework-extra">
  <TabItem value="langchain" label="LangChain" default>

<details style={{background: 'var(--ifm-color-emphasis-100)', border: '1px solid var(--ifm-color-emphasis-200)', borderRadius: '6px', padding: '0.5rem 0.75rem', marginBottom: '0.75rem'}}>
  <summary style={{cursor: 'pointer', fontWeight: 600}}>Prerequisites</summary>

1. Install: `pip install langserve`
2. Start server: `python your_langserve_app.py`
</details>

```python
from hackagent import HackAgent

# Initialize HackAgent
agent = HackAgent(
  name="my_langchain_agent",
  endpoint="http://localhost:8000",
  agent_type="langchain",
)
```

  </TabItem>
  <TabItem value="lmstudio" label="LM Studio">

<details style={{background: 'var(--ifm-color-emphasis-100)', border: '1px solid var(--ifm-color-emphasis-200)', borderRadius: '6px', padding: '0.5rem 0.75rem', marginBottom: '0.75rem'}}>
  <summary style={{cursor: 'pointer', fontWeight: 600}}>Prerequisites</summary>

1. Download from [lmstudio.ai](https://lmstudio.ai)
2. Load a model, then start local server from "Local Server" tab
</details>

```python
from hackagent import HackAgent

# Initialize HackAgent
agent = HackAgent(
  name="local-model",
  endpoint="http://localhost:1234/v1",
  agent_type="openai-sdk",
)
```

  </TabItem>
  <TabItem value="vllm" label="vLLM">

<details style={{background: 'var(--ifm-color-emphasis-100)', border: '1px solid var(--ifm-color-emphasis-200)', borderRadius: '6px', padding: '0.5rem 0.75rem', marginBottom: '0.75rem'}}>
  <summary style={{cursor: 'pointer', fontWeight: 600}}>Prerequisites</summary>

1. Install: `pip install vllm`
2. Start server: `vllm serve meta-llama/Llama-3-8B-Instruct --port 8000`
</details>

```python
from hackagent import HackAgent

# Initialize HackAgent
agent = HackAgent(
  name="my-model",
  endpoint="http://localhost:8000/v1",
  agent_type="openai-sdk",
)
```

  </TabItem>
  <TabItem value="custom" label="Custom">

<details style={{background: 'var(--ifm-color-emphasis-100)', border: '1px solid var(--ifm-color-emphasis-200)', borderRadius: '6px', padding: '0.5rem 0.75rem', marginBottom: '0.75rem'}}>
  <summary style={{cursor: 'pointer', fontWeight: 600}}>Prerequisites</summary>

1. Ensure your endpoint exposes `/v1/chat/completions` (OpenAI-compatible)
</details>

```python
from hackagent import HackAgent

# Initialize HackAgent
agent = HackAgent(
  name="my-model",
  endpoint="http://your-endpoint/v1",
  agent_type="openai-sdk",
)
```

  </TabItem>
</Tabs>

```python
# Configure and run an attack
attack_config = {
  "attack_type": "advprefix",
  "goals": ["Bypass content safety filters"]
}

agent.hack(attack_config=attack_config)
```


  </TabItem>
</Tabs>

## Next Steps

- [**Attack Tutorial**](./attack-tutorial) — Run your first security test
- [**AdvPrefix Attacks**](../attacks/advprefix) — Deep dive into attack techniques
