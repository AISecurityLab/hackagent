---
sidebar_position: 4
---

# Attack

The `hackagent attack` command executes security attacks against AI agents.

## Usage

```bash
hackagent attack <attack_type> [options]
```

## Available Attacks

| Attack Type | Description |
|-------------|-------------|
| `advprefix` | Advanced prefix injection attack |
| `baseline` | Baseline attack for comparison |

## AdvPrefix Attack

The primary attack type that generates adversarial prefixes to test agent security.

### Basic Usage

```bash
hackagent attack advprefix \
  --agent-name "my-agent" \
  --agent-type "google-adk" \
  --endpoint "http://localhost:8000" \
  --goals "Extract system prompt information"
```

### Options

| Option | Required | Description | Default |
|--------|----------|-------------|---------|
| `--agent-name` | ✅ | Name of the target agent | - |
| `--agent-type` | ✅ | Type of agent (`google-adk`, `openai-sdk`, `litellm`, `langchain`) | - |
| `--endpoint` | ✅ | Agent endpoint URL | - |
| `--goals` | ✅ | Attack goals (comma-separated or quoted string) | - |
| `--generator` | ❌ | Generator model identifier | `ollama/llama2-uncensored` |
| `--generator-endpoint` | ❌ | Generator endpoint URL | `http://localhost:11434/api/generate` |
| `--judge` | ❌ | Judge model identifier | `ollama/llama3` |
| `--judge-endpoint` | ❌ | Judge endpoint URL | `http://localhost:11434/api/generate` |
| `--max-iterations` | ❌ | Maximum attack iterations | 10 |
| `--temperature` | ❌ | Sampling temperature | 0.7 |
| `--output-format` | ❌ | Output format (`table`, `json`, `csv`) | Config default |

### Examples

**Basic attack:**

```bash
hackagent attack advprefix \
  --agent-name "weather-bot" \
  --agent-type "google-adk" \
  --endpoint "http://localhost:8000" \
  --goals "Return fake weather data"
```

**Attack with custom models:**

```bash
hackagent attack advprefix \
  --agent-name "assistant" \
  --agent-type "openai-sdk" \
  --endpoint "https://api.example.com/v1" \
  --goals "Extract sensitive information" \
  --generator "ollama/mistral-uncensored" \
  --generator-endpoint "http://localhost:11434/api/generate" \
  --judge "ollama/llama3" \
  --judge-endpoint "http://localhost:11434/api/generate"
```

**Attack with multiple goals:**

```bash
hackagent attack advprefix \
  --agent-name "support-bot" \
  --agent-type "litellm" \
  --endpoint "http://localhost:8000" \
  --goals "Bypass content filters" "Extract system prompt" "Ignore safety instructions"
```

**High-intensity attack:**

```bash
hackagent attack advprefix \
  --agent-name "target-agent" \
  --agent-type "google-adk" \
  --endpoint "http://localhost:8000" \
  --goals "Comprehensive security test" \
  --max-iterations 50 \
  --temperature 0.9
```

## Baseline Attack

A simpler attack for comparison purposes.

```bash
hackagent attack baseline \
  --agent-name "my-agent" \
  --agent-type "google-adk" \
  --endpoint "http://localhost:8000" \
  --goals "Test agent response"
```

## Output

Attack results are:

1. **Displayed in the terminal** — Progress and summary
2. **Saved locally** — In `./logs/runs/` directory
3. **Uploaded to dashboard** — View at [app.hackagent.dev](https://app.hackagent.dev)

### JSON Output

For CI/CD integration, output results as JSON:

```bash
hackagent attack advprefix \
  --agent-name "target" \
  --agent-type "google-adk" \
  --endpoint "http://localhost:8000" \
  --goals "Security test" \
  --output-format json > results.json
```

## CI/CD Integration

Example GitHub Actions workflow:

```yaml
- name: Run Security Tests
  run: |
    hackagent attack advprefix \
      --agent-name "${{ env.AGENT_NAME }}" \
      --agent-type "google-adk" \
      --endpoint "${{ env.AGENT_ENDPOINT }}" \
      --goals "Automated security validation" \
      --output-format json > test_results.json

- name: Upload Results
  uses: actions/upload-artifact@v3
  with:
    name: security-results
    path: test_results.json
```

## See Also

- [Attack Tutorial](../getting-started/attack-tutorial.md) — Step-by-step guide
- [AdvPrefix Attacks](../attacks/advprefix-attacks.md) — Detailed attack documentation
- [Results](./results.md) — View and manage attack results
