---
sidebar_position: 2
---

# Initialization

The `hackagent init` command provides an interactive setup wizard to configure HackAgent for first-time use.

## Usage

```bash
hackagent init
```

## What It Does

The initialization wizard will:

1. **Display the HackAgent ASCII logo**
2. **Prompt for your API key** *(optional)* — Get yours at [app.hackagent.dev](https://app.hackagent.dev). **Press Enter to skip and use local mode.**
3. **Set verbosity level** — Control logging detail (0=ERROR to 3=DEBUG)
4. **Test configuration** — Verify API connection (skipped when no key is provided)
5. **Save configuration** — Stored in `~/.config/hackagent/config.json`

:::info API key is optional
HackAgent works fully without an API key. When no key is provided, results are stored locally in `~/.local/share/hackagent/hackagent.db` and no data is sent to any remote server. Provide an API key only if you want cloud storage and the [app.hackagent.dev](https://app.hackagent.dev) dashboard.
:::

## Example Session

```bash
$ hackagent init

╭────────────────────────────────────────────────────────────────────────────────╮
│                                                                                │
│  ██╗  ██╗ █████╗  ██████╗██╗  ██╗ █████╗  ██████╗ ███████╗███╗   ██╗████████╗  │
│  ██║  ██║██╔══██╗██╔════╝██║ ██╔╝██╔══██╗██╔════╝ ██╔════╝████╗  ██║╚══██╔══╝  │
│  ███████║███████║██║     █████╔╝ ███████║██║  ███╗█████╗  ██╔██╗ ██║   ██║     │
│  ██╔══██║██╔══██║██║     ██╔═██╗ ██╔══██║██║   ██║██╔══╝  ██║╚██╗██║   ██║     │
│  ██║  ██║██║  ██║╚██████╗██║  ██╗██║  ██║╚██████╔╝███████╗██║ ╚████║   ██║     │
│  ╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝  ╚═══╝   ╚═╝     │
│                                                                                │
╰────────────────────────────────────────────────────────────────────────────────╯

🔧 HackAgent CLI Setup Wizard
Welcome! Let's get you set up for AI agent security testing.

📋 API Key Configuration (optional)
Get your API key from: https://app.hackagent.dev
Leave blank to run in local mode (results stored in ~/.local/share/hackagent/hackagent.db)
Enter API key (press Enter to skip): ****************************************

 Verbosity Level Configuration
0 = ERROR (only errors)
1 = WARNING (errors + warnings)
2 = INFO (errors + warnings + info)
3 = DEBUG (all messages)
Default verbosity level [3]: 0

✅ Configuration saved

🔍 Testing configuration...
✅ Setup complete! API connection verified.

💡 Next steps:
  hackagent attack advprefix --help
  hackagent agent list
```

:::tip No API key? That's fine!
If you pressed Enter at the API key prompt, the wizard skips the connection test and HackAgent runs in **local mode**. You can start testing immediately — no account needed.
:::

## Options

| Option | Description |
|--------|-------------|
| `--help` | Show help message |

## Configuration File

After initialization, your configuration is saved to `~/.config/hackagent/config.json`:

```json
{
  "api_key": "your-api-key-here",
  "verbose": 0
}
```

The `api_key` field is **optional**. If omitted (or left as `null`), HackAgent runs in local mode:

```json
{
  "verbose": 0
}
```

## Re-initialization

You can run `hackagent init` again at any time to update your configuration. It will overwrite the existing settings.

## Next Steps

After initialization:

1. **Verify your setup**: `hackagent config show`
2. **Run your first attack**: See [Attack](./attack.md)
3. **View results**: See [Results](./results.md)
