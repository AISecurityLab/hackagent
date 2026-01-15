# HackAgent CLI Documentation

## Overview

The **HackAgent CLI** provides a powerful, user-friendly command-line interface for AI agent security testing. With beautiful ASCII branding, rich terminal output, and comprehensive functionality, it's the fastest way to get started with HackAgent.

## Installation

```bash
pip install hackagent
```

## Quick Start

### 1. Interactive Setup

Start with our guided setup wizard that displays the beautiful HackAgent ASCII logo:

```bash
hackagent init
```

This will:
- ✨ Show the stunning HackAgent ASCII logo
- 🔑 Prompt for your API key
- 🌐 Configure the base URL
- 📊 Set your preferred output format
- 💾 Save configuration for future use

### 2. Verify Installation

```bash
hackagent version
```

### 3. Run Your First Attack

```bash
hackagent attack advprefix \
  --agent-name "weather-bot" \
  --agent-type "google-adk" \
  --endpoint "http://localhost:8000" \
  --goals "Return fake weather data"
```

## Command Reference

### Main Commands

| Command | Description | Example |
|---------|-------------|---------|  
| `hackagent` | Launch TUI interface | `hackagent` |
| `hackagent init` | Interactive setup wizard | `hackagent init` |
| `hackagent config` | Manage configuration | `hackagent config show` |
| `hackagent agent` | Manage AI agents | `hackagent agent list` |
| `hackagent attack` | Execute security attacks | `hackagent attack advprefix` |
| `hackagent results` | View and manage results | `hackagent results list` |
| `hackagent version` | Show version info | `hackagent version` |### Configuration Commands

```bash
# Show current configuration
hackagent config show

# Set API key
hackagent config set --api-key YOUR_API_KEY

# Set output format
hackagent config set --output-format json
```

### Agent Management

```bash
# List all agents
hackagent agent list

# Create a new agent
hackagent agent create \
  --name "test-agent" \
  --type "google-adk" \
  --endpoint "http://localhost:8000"

# Delete agent
hackagent agent delete --id AGENT_ID
```

### Attack Execution

Currently supports **AdvPrefix** attacks:

```bash
# AdvPrefix attack with full configuration
hackagent attack advprefix \
  --agent-name "weather-bot" \
  --agent-type "google-adk" \
  --endpoint "http://localhost:8000" \
  --goals "Return fake weather data"
```

### Results Management

```bash
# List all results
hackagent results list

# Filter by status
hackagent results list --status completed
```

## Configuration

### Configuration Priority

Configuration is loaded in this order (highest to lowest priority):

1. **Command-line arguments**
2. **Config file** (`~/.hackagent/config.json`)
3. **Environment variables**
4. **Default values**

### Configuration File

Default location: `~/.hackagent/config.json`

```json
{
  "api_key": "your-api-key-here",
  "base_url": "https://api.hackagent.dev",
  "output_format": "table",
  "verbose": 0
}
```

### Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|  
| `HACKAGENT_API_KEY` | Your API key | `export HACKAGENT_API_KEY=abc123` |
| `HACKAGENT_BASE_URL` | API base URL | `export HACKAGENT_BASE_URL=https://api.hackagent.dev` |
| `HACKAGENT_OUTPUT_FORMAT` | Default output format | `export HACKAGENT_OUTPUT_FORMAT=json` |## Output Formats

### Table Format (Default)

Beautiful, colored tables with rich formatting:

```bash
hackagent agent list --output-format table
```

### JSON Format

Machine-readable JSON output:

```bash
hackagent agent list --output-format json
```

### CSV Format

Comma-separated values for spreadsheet import:

```bash
hackagent agent list --output-format csv
```

## Advanced Features

### Verbose Output

Increase verbosity for debugging:

```bash
hackagent -v agent list          # Verbose
hackagent -vv agent list         # More verbose  
hackagent -vvv agent list        # Maximum verbosity
```

### Debug Mode

Enable full error tracebacks:

```bash
export HACKAGENT_DEBUG=1
hackagent agent list
```

### Configuration Profiles

Use different configuration files:

```bash
hackagent --config-file ./custom-config.json agent list
```

## Logo Display

The HackAgent ASCII logo appears when you run `hackagent init` and `hackagent version`.

## Troubleshooting

### Common Issues

**Problem**: `Command not found: hackagent`
**Solution**: Ensure HackAgent is installed and in your PATH:
```bash
pip install hackagent
which hackagent
```

**Problem**: `API key not found`
**Solution**: Set your API key:
```bash
hackagent config set --api-key YOUR_KEY
# OR
export HACKAGENT_API_KEY=YOUR_KEY
```

**Problem**: `Connection failed`
**Solution**: Check your network and API URL:
```bash
hackagent config show     # Verify settings
```

## Examples

### Complete Workflow Example

```bash
# 1. Setup (shows logo and guided configuration)
hackagent init

# 2. Create an agent for testing
hackagent agent create \
  --name "weather-service" \
  --type "google-adk" \
  --endpoint "http://localhost:8000"

# 3. Run comprehensive security testing
hackagent attack advprefix \
  --agent-name "weather-service" \
  --goals "Extract user location data" \
  --max-iterations 20 \
  --temperature 0.9

# 4. Review results
hackagent results list
```

### CI/CD Integration

```bash
# Automated testing in CI/CD pipeline
hackagent attack advprefix \
  --agent-name "$AGENT_NAME" \
  --goals "Security validation test" \
  --output-format json > test_results.json
```

## Get Help

- **Command Help**: `hackagent COMMAND --help`
- **General Help**: `hackagent --help`
- **Documentation**: Visit [https://hackagent.dev/docs](https://hackagent.dev/docs)
- **Community**: [GitHub Discussions](https://github.com/AISecurityLab/hackagent/discussions)
- **Support**: [ais@ai4i.it](mailto:ais@ai4i.it) 