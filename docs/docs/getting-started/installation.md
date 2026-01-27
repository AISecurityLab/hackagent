---
sidebar_position: 1
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

# Installation

Get HackAgent up and running in seconds.

## Quick Install

### Requirements

- **Python 3.10+**
- **pip** or **uv** package manager

### Production Installation

<Tabs>
  <TabItem value="uv" label="uv (Recommended)" default>

```bash
uv add hackagent
```

  </TabItem>
  <TabItem value="pip" label="pip">

```bash
pip install hackagent
```

  </TabItem>
</Tabs>

### Verify Installation

After installation, verify everything works:

```bash
hackagent --version
```

### Initial Setup

After installation, run the interactive setup wizard:

```bash
hackagent init
```

This will guide you through:
1. 🔑 **Enter your API key** — Get yours at [app.hackagent.dev](https://app.hackagent.dev)
2. 📊 **Set output format** — Choose between `table`, `json`, or `csv`
3. 🔊 **Set verbosity level** — Control logging detail (0=ERROR to 3=DEBUG)
4. 💾 **Save configuration** — Stored securely for future use

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

---

## Next Steps

- [**Quick Start**](./quick-start) — Get started in minutes
- [**Attack Tutorial**](./attack-tutorial) — Run your first security test
- [**CLI Reference**](../cli/overview) — Command-line interface documentation
