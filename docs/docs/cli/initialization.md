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

1. 🎨 **Display the HackAgent ASCII logo**
2. 🔑 **Prompt for your API key** — Get yours at [app.hackagent.dev](https://app.hackagent.dev)
3. 📊 **Set output format** — Choose between `table`, `json`, or `csv`
4. 🔊 **Set verbosity level** — Control logging detail (0=ERROR to 3=DEBUG)
5. 🔍 **Test configuration** — Verify API connection
6. 💾 **Save configuration** — Stored securely in `~/.config/hackagent/config.json`

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

📋 API Key Configuration
Get your API key from: https://app.hackagent.dev
Enter API key: ****************************************

📊 Output Format Configuration
Default output format (table, json, csv) [table]: table

🔊 Verbosity Level Configuration
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

## Options

| Option | Description |
|--------|-------------|
| `--help` | Show help message |

## Configuration File

After initialization, your configuration is saved to `~/.config/hackagent/config.json`:

```json
{
  "api_key": "your-api-key-here",
  "output_format": "table",
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
