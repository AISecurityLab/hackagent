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
| `hackagent` | Show welcome screen with logo | `hackagent` |
| `hackagent init` | Interactive setup wizard | `hackagent init` |
| `hackagent config` | Manage configuration | `hackagent config show` |
| `hackagent agent` | Manage AI agents | `hackagent agent list` |
| `hackagent attack` | Execute security attacks | `hackagent attack advprefix` |
| `hackagent results` | View and manage results | `hackagent results list` |
| `hackagent version` | Show version and config info | `hackagent version` |
| `hackagent doctor` | Diagnose configuration issues | `hackagent doctor` |

### Configuration Commands

```bash
# Show current configuration
hackagent config show

# Set API key
hackagent config set --api-key YOUR_API_KEY

# Set base URL
hackagent config set --base-url https://hackagent.dev

# Set default output format
hackagent config set --output-format json

# Validate configuration
hackagent config validate

# Reset to defaults
hackagent config reset
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

# Show agent details
hackagent agent show --id AGENT_ID

# Update agent
hackagent agent update --id AGENT_ID --name "new-name"

# Delete agent
hackagent agent delete --id AGENT_ID
```

### Attack Execution

```bash
# AdvPrefix attack with minimal options
hackagent attack advprefix --agent-name "my-bot"

# AdvPrefix attack with full configuration
hackagent attack advprefix \
  --agent-name "weather-bot" \
  --agent-type "google-adk" \
  --endpoint "http://localhost:8000" \
  --goals "Return fake weather data" \
  --max-iterations 10 \
  --batch-size 5 \
  --temperature 0.8

# List available attack types
hackagent attack list

# Get help for specific attack
hackagent attack advprefix --help
```

### Results Management

```bash
# List all results
hackagent results list

# Show specific result
hackagent results show --id RESULT_ID

# Export results to file
hackagent results export --format json --output results.json

# Filter results
hackagent results list --status "success" --attack-type "advprefix"

# Delete results
hackagent results delete --id RESULT_ID
```

## Configuration

### Configuration Sources

The CLI loads configuration from multiple sources in order of precedence:

1. **Command-line arguments** (highest priority)
2. **Environment variables**
3. **Configuration file**
4. **Default values** (lowest priority)

### Configuration File

Default location: `~/.hackagent/config.json`

```json
{
  "api_key": "your-api-key-here",
  "base_url": "https://hackagent.dev",
  "output_format": "table",
  "verbose": 0
}
```

### Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `HACKAGENT_API_KEY` | Your API key | `export HACKAGENT_API_KEY=abc123` |
| `HACKAGENT_BASE_URL` | API base URL | `export HACKAGENT_BASE_URL=https://hackagent.dev` |
| `HACKAGENT_OUTPUT_FORMAT` | Default output format | `export HACKAGENT_OUTPUT_FORMAT=json` |
| `HACKAGENT_DEBUG` | Enable debug mode | `export HACKAGENT_DEBUG=1` |

## Output Formats

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
hackagent --config-file ./production.json agent list
```

### Batch Operations

Process multiple items efficiently:

```bash
# Export all results
hackagent results export --format json --output all_results.json

# Delete multiple results
hackagent results delete --batch --status "failed"
```

## Logo Integration

The beautiful HackAgent ASCII logo appears automatically when you:

- Run `hackagent` with no arguments (welcome screen)
- Execute `hackagent attack` commands
- Use `hackagent agent` commands  
- View `hackagent results`
- Run `hackagent version`
- Start `hackagent init` setup

The logo displays once per command session to provide branding without overwhelming the output.

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
hackagent doctor          # Diagnose issues
hackagent config show     # Verify settings
```

### Diagnostic Tool

Use the built-in diagnostic tool to check your setup:

```bash
hackagent doctor
```

This will verify:
- ✅ Configuration file exists
- ✅ API key is set and valid
- ✅ Network connectivity
- ✅ Required dependencies

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

# 4. Review results with rich formatting
hackagent results list

# 5. Export findings for reporting
hackagent results export \
  --format json \
  --output security_report.json
```

### CI/CD Integration

```bash
# Automated testing in CI/CD pipeline
hackagent attack advprefix \
  --agent-name "$AGENT_NAME" \
  --goals "Security validation test" \
  --output-format json \
  --max-iterations 5 > test_results.json

# Check if any critical vulnerabilities found
if hackagent results list --status "critical" --output-format json | jq '.count > 0'; then
  echo "Critical vulnerabilities found!"
  exit 1
fi
```

## Get Help

- **Command Help**: `hackagent COMMAND --help`
- **General Help**: `hackagent --help`
- **Documentation**: Visit [https://hackagent.dev/docs](https://hackagent.dev/docs)
- **Community**: [GitHub Discussions](https://github.com/AISecurityLab/hackagent/discussions)
- **Support**: [ais@ai4i.it](mailto:ais@ai4i.it) 