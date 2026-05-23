---
sidebar_position: 2
---

# Initialization

The `hackagent init` command provides an interactive setup wizard to configure local HackAgent preferences for first-time use.

## Usage

```bash
hackagent init
```

## What It Does

The initialization wizard will:

1. **Display the HackAgent ASCII logo**
2. **Set verbosity level** — Control logging detail (0=ERROR to 3=DEBUG)
3. **Save configuration** — Stored in `~/.config/hackagent/config.json`
HACKAGENT_BANNER = """

"""
## Example Session

```bash
$ hackagent init

╭──────────────────────────────────────────────────────────────────────────────────╮
│                                                                                  │
│   ██╗  ██╗ █████╗  ██████╗██╗  ██╗ █████╗  ██████╗ ███████╗███╗   ██╗████████╗   │
│   ██║  ██║██╔══██╗██╔════╝██║ ██╔╝██╔══██╗██╔════╝ ██╔════╝████╗  ██║╚══██╔══╝   │
│   ███████║███████║██║     █████╔╝ ███████║██║  ███╗█████╗  ██╔██╗ ██║   ██║      │
│   ██╔══██║██╔══██║██║     ██╔═██╗ ██╔══██║██║   ██║██╔══╝  ██║╚██╗██║   ██║      │  
│   ██║  ██║██║  ██║╚██████╗██║  ██╗██║  ██║╚██████╔╝███████╗██║ ╚████║   ██║      │
│   ╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝  ╚═══╝   ╚═╝      │
│                                                                                  │
╰──────────────────────────────────────────────────────────────────────────────────╯

🔧 HackAgent CLI Setup Wizard
Welcome! Let's get you set up for AI agent security testing.


🔊 Verbosity Level Configuration
0 = ERROR (only errors)
1 = WARNING (errors + warnings) 
2 = INFO (errors + warnings + info)
3 = DEBUG (all messages)
Default verbosity level [0]: 1

✅ Configuration saved
✅ Setup complete! (Local mode: results stored in ~/.local/share/hackagent/hackagent.db)
```

## Options

| Option | Description |
|--------|-------------|
| `--help` | Show help message |

## Configuration File

After initialization, your configuration is saved to `~/.config/hackagent/config.json`:

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
2. **Run your first attack**: See [Attack](./attack.mdx)
3. **View results**: See [Results](./results.md)
