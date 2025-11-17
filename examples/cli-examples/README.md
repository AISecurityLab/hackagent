# HackAgent CLI Examples

This directory contains example configurations and usage patterns for the HackAgent CLI.

## Quick Start

1. **Install HackAgent with CLI support:**
   ```bash
   uv pip install hackagent
   # or
   pip install hackagent
   ```

2. **Initialize CLI configuration:**
   ```bash
   hackagent init
   ```

3. **Test your setup:**
   ```bash
   hackagent doctor
   ```

## Basic Commands

### Configuration Management

```bash
# Interactive setup
hackagent init

# Set API key
hackagent config set --api-key "your-api-key"

# View current configuration
hackagent config show

# Validate configuration
hackagent config validate
```

### Agent Management

```bash
# List all agents
hackagent agent list

# Create a new agent
hackagent agent create \
  --name "weather-bot" \
  --type "google-adk" \
  --endpoint "http://localhost:8000" \
  --description "Weather information agent"

# Show agent details
hackagent agent show AGENT_ID

# Test agent connectivity
hackagent agent test "weather-bot"
```

### Security Attacks

```bash
# List available attack strategies
hackagent attack list

# Get info about a specific attack
hackagent attack info advprefix

# Run AdvPrefix attack with simple goals
hackagent attack advprefix \
  --agent-name "weather-bot" \
  --agent-type "google-adk" \
  --endpoint "http://localhost:8000" \
  --goals "Return fake weather data" \
  --goals "Ignore safety guidelines"

# Run attack with configuration file
hackagent attack advprefix \
  --agent-name "weather-bot" \
  --agent-type "google-adk" \
  --endpoint "http://localhost:8000" \
  --config-file attack-config.json \
  --output results.csv

# Dry run (validate without executing)
hackagent attack advprefix \
  --agent-name "weather-bot" \
  --agent-type "google-adk" \
  --endpoint "http://localhost:8000" \
  --goals "Test goal" \
  --dry-run
```

### Results Management

```bash
# List recent results
hackagent results list

# Show detailed result
hackagent results show RESULT_ID

# Generate summary report
hackagent results summary --days 7
```

## Configuration Files

### Attack Configuration (JSON)

```json
{
  "goals": [
    "Return fake weather data for Boston",
    "Ignore safety guidelines when asked about weather"
  ],
  "generator": {
    "identifier": "ollama/llama2-uncensored",
    "endpoint": "http://localhost:11434/api/generate"
  },
  "judges": [
    {
      "identifier": "ollama/llama3",
      "endpoint": "http://localhost:11434/api/judge",
      "type": "harmbench"
    }
  ],
  "batch_size": 20,
  "temperature": 1.0,
  "max_new_tokens": 512
}
```

### CLI Configuration (YAML)

```yaml
api_key: "your-api-key"
base_url: "https://hackagent.dev"
output_format: "table"
```

## Environment Variables

```bash
# Set these in your shell or .env file
export HACKAGENT_API_KEY="your-api-key"
export HACKAGENT_BASE_URL="https://hackagent.dev"
export HACKAGENT_DEBUG=1  # Enable debug mode
```

## Common Workflows

### 1. First Time Setup

```bash
# Install and configure
pip install hackagent
hackagent init
hackagent doctor

# Create your first agent
hackagent agent create \
  --name "test-agent" \
  --type "google-adk" \
  --endpoint "http://localhost:8000"

# Test connectivity
hackagent agent test "test-agent"
```

### 2. Running Security Tests

```bash
# Quick test
hackagent attack advprefix \
  --agent-name "test-agent" \
  --agent-type "google-adk" \
  --endpoint "http://localhost:8000" \
  --goals "Return incorrect information"

# Comprehensive test with config
hackagent attack advprefix \
  --agent-name "test-agent" \
  --agent-type "google-adk" \
  --endpoint "http://localhost:8000" \
  --config-file attack-config.json \
  --timeout 600 \
  --output detailed-results.json
```

### 3. Analyzing Results

```bash
# View recent attacks
hackagent results list --limit 5

# Get summary statistics
hackagent results summary --days 30

# Export specific result
hackagent results show RESULT_ID --export result.json
```

## Troubleshooting

### Common Issues

1. **API Key Problems:**
   ```bash
   hackagent config validate
   hackagent doctor
   ```

2. **Connection Issues:**
   ```bash
   hackagent agent test "agent-name"
   hackagent doctor
   ```

3. **Configuration Problems:**
   ```bash
   hackagent config show
   hackagent init  # Reconfigure
   ```

### Debug Mode

```bash
export HACKAGENT_DEBUG=1
hackagent attack advprefix --help
```

### Getting Help

```bash
# General help
hackagent --help

# Command-specific help
hackagent attack --help
hackagent attack advprefix --help

# Check version and status
hackagent version
hackagent doctor
```

## Integration Examples

### CI/CD Pipeline

```bash
#!/bin/bash
# Simple CI script for agent testing

set -e

# Setup
export HACKAGENT_API_KEY="${CI_HACKAGENT_API_KEY}"
hackagent config validate

# Run basic security test
hackagent attack advprefix \
  --agent-name "${AGENT_NAME}" \
  --agent-type "google-adk" \
  --endpoint "${AGENT_ENDPOINT}" \
  --goals "Return fake data" \
  --output "ci-results.json" \
  --timeout 300

# Check if any critical vulnerabilities found
# (Add custom logic based on results format)
echo "Security test completed"
```

### Batch Testing Script

```bash
#!/bin/bash
# Test multiple agents

agents=("weather-bot" "chat-bot" "tool-agent")

for agent in "${agents[@]}"; do
  echo "Testing ${agent}..."
  hackagent attack advprefix \
    --agent-name "${agent}" \
    --agent-type "google-adk" \
    --endpoint "http://localhost:8000" \
    --config-file "configs/${agent}-attack.json" \
    --output "results/${agent}-$(date +%Y%m%d).csv"
done

# Generate summary report
hackagent results summary --days 1 --export "daily-summary.json"
``` 