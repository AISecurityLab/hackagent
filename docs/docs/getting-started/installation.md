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

HackAgent works **out of the box without any account or API key**. All results are stored locally in a SQLite database at `~/.local/share/hackagent/hackagent.db`.

Optionally, run the interactive setup wizard to configure preferences or connect to the cloud platform:

```bash
hackagent init
```

This will guide you through:
1. **Enter your API key** *(optional)* — Connects to [app.hackagent.dev](https://app.hackagent.dev) for cloud storage and dashboards. **Leave blank to stay in local mode.**
2. **Set output format** — Choose between `table`, `json`, or `csv`
3. **Set verbosity level** — Control logging detail (0=ERROR to 3=DEBUG)
4. **Save configuration** — Stored in `~/.config/hackagent/config.json`

:::info Local mode (no API key required)
When no API key is configured, HackAgent runs entirely offline. Results are stored in `~/.local/share/hackagent/hackagent.db` and are fully accessible via `hackagent results list` and the TUI. No data is sent to any remote server.
:::

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
