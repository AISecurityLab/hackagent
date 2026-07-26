---
sidebar_position: 5
---

# Results

The `hackagent results` command lets you browse and summarize attack results stored in your local HackAgent database (`~/.local/share/hackagent/hackagent.db` by default).

## Commands

### List Results

```bash
hackagent results list
```

This launches the interactive TUI directly on the **Results** tab, where you can browse, filter, and drill into individual runs.

| Option | Description | Example |
|--------|-------------|---------|
| `--limit` | Number of results to show (default: `10`) | `--limit 25` |
| `--status` | Filter by status: `pending`, `running`, `completed`, `failed` | `--status completed` |
| `--agent` | Filter by agent name | `--agent "weather-bot"` |
| `--attack-type` | Filter by attack type | `--attack-type advprefix` |

### Show Result Details

View detailed information about a specific result by its ID (a UUID, as shown in the TUI or `results summary` output):

```bash
hackagent results show <result_id>
```

**Example:**

```bash
hackagent results show 3fa85f64-5717-4562-b3fc-2c963f66afa6
```

This prints a table with the result's ID, agent name, attack type, status, and creation time, followed by any additional stored result data (as JSON).

### Summary Statistics

Show aggregate statistics across recent results:

```bash
hackagent results summary
```

| Option | Description | Example |
|--------|-------------|---------|
| `--status` | Filter by status: `pending`, `running`, `completed`, `failed` | `--status completed` |
| `--agent` | Filter by agent name | `--agent "weather-bot"` |
| `--attack-type` | Filter by attack type | `--attack-type advprefix` |
| `--days` | Number of days to include (default: `7`) | `--days 30` |

**Example:**

```bash
hackagent results summary --days 30 --status completed
```

Prints a breakdown by status, by agent, and by attack type, plus average Majority Vote ASR and Fleiss' Kappa across the matched results.

## Local Storage

By default, results live in a local SQLite database at `~/.local/share/hackagent/hackagent.db` (via `LocalBackend`). If you've configured a HackAgent Cloud API key, results are instead written to your organization's account on `https://api.hackagent.dev` (via `RemoteBackend`), viewable on the hosted dashboard.

## See Also

- [Attack](./attack.mdx) — Run security attacks
- [Config](./config.md) — Configure HackAgent settings
