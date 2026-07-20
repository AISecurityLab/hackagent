---
sidebar_position: 7
---

# Agent

The `hackagent agent` command manages agents registered with HackAgent (target endpoints you've configured for testing).

## Commands

Every `agent` subcommand currently opens the interactive TUI directly on the **Agents** tab — arguments/options are validated but the actual list/create/show/update/delete/test actions happen inside the TUI, not headlessly on the command line.

```bash
hackagent agent list
hackagent agent create --name "my-agent" --type openai-sdk --endpoint "http://localhost:8000/v1"
hackagent agent show <agent_id>
hackagent agent update <agent_id> --name "renamed-agent"
hackagent agent delete <agent_id>
hackagent agent test <agent_name>
```

| Subcommand | Arguments/Options | Description |
|---|---|---|
| `list` | — | Open the Agents tab to browse registered agents |
| `create` | `--name`, `--type` (`google-adk`\|`litellm`\|`openai-sdk`\|`ollama`), `--endpoint`, `--description`, `--metadata` | Open the Agents tab to create a new agent |
| `show` | `agent_id` | Open the Agents tab to inspect a specific agent |
| `update` | `agent_id`, `--name`, `--endpoint`, `--description`, `--metadata` | Open the Agents tab to update a specific agent |
| `delete` | `agent_id`, `--confirm` | Open the Agents tab to delete a specific agent |
| `test` | `agent_name` | Open the Agents tab to test connectivity to a specific agent |

## See Also

- [Attack](./attack.mdx) — Run security attacks against a configured agent
- [Web](./web.md) — Launch the local dashboard directly
