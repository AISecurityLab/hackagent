---
sidebar_position: 1
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

# Installation

Get HackAgent up and running in seconds.

## Requirements

- **Python 3.10+**
- **pip** or **uv** package manager

## Production Installation

<Tabs>
  <TabItem value="uv" label="uv (Recommended)" default>

```bash
uv add hackagent
```

Or using pip with uv:

```bash
uv pip install hackagent
```

  </TabItem>
  <TabItem value="pip" label="pip">

```bash
pip install hackagent
```

  </TabItem>
</Tabs>

## Verify Installation

After installation, verify everything works:

```bash
hackagent --version
```

## Development Installation

For development or to access the latest features:

<Tabs>
  <TabItem value="uv-dev" label="uv (Recommended)" default>

```bash
# Clone the repository
git clone https://github.com/AISecurityLab/hackagent.git
cd hackagent

# Install with uv
uv sync --group dev
```

  </TabItem>
  <TabItem value="pip-dev" label="pip">

```bash
# Clone the repository
git clone https://github.com/AISecurityLab/hackagent.git
cd hackagent

# Install in development mode
pip install -e ".[dev]"
```

  </TabItem>
</Tabs>

## Initial Setup

After installation, run the interactive setup wizard:

```bash
hackagent init
```

This will guide you through:
1. 🔑 **Enter your API key** — Get yours at [app.hackagent.dev](https://app.hackagent.dev)
2. 🌐 **Configure the base URL** — Default: `https://api.hackagent.dev`
3. 📊 **Set output format** — Choose between `table`, `json`, or `csv`
4. 💾 **Save configuration** — Stored securely for future use

## Optional Dependencies

### For Local LLM Support

If you plan to use local models with Ollama:

```bash
# Install Ollama (macOS/Linux)
curl -fsSL https://ollama.com/install.sh | sh

# Pull recommended models
ollama pull llama3
ollama pull llama2-uncensored
```

### For Development

```bash
# Install development dependencies
uv sync --group dev

# Or with pip
pip install -e ".[dev]"
```

---

## Next Steps

- [**How to Use HackAgent**](../HowTo) — Step-by-step usage guide
- [**Attack Tutorial**](../tutorial-basics/attack-tutorial) — Run your first security test
- [**Python SDK**](../sdk/python-quickstart) — Full SDK documentation
