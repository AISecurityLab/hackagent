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
2. **Ask whether to enable remote mode** — Local mode (default) needs no API key and stores results in a local SQLite database; remote mode prompts for a HackAgent API key and syncs results to `https://api.hackagent.dev`. If you enable remote mode but leave the key blank, it falls back to local mode.
3. **Set verbosity level** — Control logging detail (0=ERROR to 3=DEBUG)
4. **Save configuration** — Stored in `~/.config/hackagent/config.json`

If a configuration file already exists, you'll be asked whether to overwrite it before the wizard continues.

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

☁️ Mode Configuration
Local mode (default): no API key required
Remote mode: requires HackAgent API key for cloud sync
Enable remote mode (cloud sync)? [y/N]: n

🔊 Verbosity Level Configuration
0 = ERROR (only errors)
1 = WARNING (errors + warnings) [default]
2 = INFO (errors + warnings + info)
3 = DEBUG (all messages)
Default verbosity level [1]: 1

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
