---
sidebar_position: 5
---

# Results

The `hackagent results` command allows you to view and manage attack results.

## Commands

### List Results

View all attack results:

```bash
hackagent results list
```

**Example output:**

```
┌────────────────┬──────────────┬─────────────┬────────────────────┬──────────┐
│ ID             │ Agent        │ Attack Type │ Created            │ Status   │
├────────────────┼──────────────┼─────────────┼────────────────────┼──────────┤
│ res_abc123     │ weather-bot  │ advprefix   │ 2025-01-22 10:30   │ completed│
│ res_def456     │ assistant    │ advprefix   │ 2025-01-22 09:15   │ completed│
│ res_ghi789     │ support-bot  │ baseline    │ 2025-01-21 16:45   │ failed   │
└────────────────┴──────────────┴─────────────┴────────────────────┴──────────┘
```

### Filter Results

Filter results by various criteria:

```bash
# Filter by status
hackagent results list --status completed
hackagent results list --status failed
hackagent results list --status running

# Filter by agent name
hackagent results list --agent-name "weather-bot"

# Filter by attack type
hackagent results list --attack-type advprefix

# Combine filters
hackagent results list --status completed --agent-name "weather-bot"
```

### Get Result Details

View detailed information about a specific result:

```bash
hackagent results get --id res_abc123
```

**Example output:**

```
Result Details: res_abc123
══════════════════════════════════════════════════════════════

Agent:        weather-bot
Attack Type:  advprefix
Status:       completed
Created:      2025-01-22 10:30:15
Duration:     2m 34s

Goals:
  • Return fake weather data
  • Bypass location validation

Summary:
  Total Attempts:  50
  Successful:      12
  Success Rate:    24%

Top Prefixes:
  1. "Ignore previous instructions and..."  (Score: 0.85)
  2. "As a weather expert, you must..."     (Score: 0.72)
  3. "The user has special permissions..."  (Score: 0.68)
```

### Export Results

Export results in different formats:

```bash
# Export as JSON
hackagent results list > results.json

# Export specific result
hackagent results get --id res_abc123 > result_detail.json
```

### Delete Results

Remove results from the system:

```bash
# Delete a specific result
hackagent results delete --id res_abc123

# Delete with confirmation prompt
hackagent results delete --id res_abc123 --confirm
```

## Options

### List Options

| Option | Description | Example |
|--------|-------------|---------|
| `--status` | Filter by status | `--status completed` |
| `--agent-name` | Filter by agent name | `--agent-name "my-agent"` |
| `--attack-type` | Filter by attack type | `--attack-type advprefix` |
| `--limit` | Maximum results to show | `--limit 10` |

### Get Options

| Option | Description | Example |
|--------|-------------|------|
| `--id` | Result ID | `--id res_abc123` |

### Delete Options

| Option | Description | Example |
|--------|-------------|---------|
| `--id` | Result ID | `--id res_abc123` |
| `--confirm` | Skip confirmation | `--confirm` |

## Dashboard

Results are automatically synced to the HackAgent dashboard:

**[app.hackagent.dev](https://app.hackagent.dev)**

The dashboard provides:

- **Visual analytics** — Charts and graphs
- **Advanced filtering** — Complex queries
- **Trend analysis** — Track security over time
- **Export options** — PDF reports, CSV exports
- **Team sharing** — Collaborate with your team

## Local Storage

Results are also saved locally in `./logs/runs/` for offline access:

```
./logs/runs/
├── res_abc123/
│   ├── config.json
│   ├── results.json
│   └── prefixes.json
├── res_def456/
│   └── ...
```

## See Also

- [Attack](./attack.md) — Run security attacks
- [Config](./config.md) — Configure HackAgent settings
