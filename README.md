<div align="center">
<p align="center">
  <img src="https://docs.hackagent.dev/img/banner.svg" alt="HackAgent - AI Agent Security Testing Toolkit" width="800">
</p>

  <strong>AI Security Red-Team Toolkit</strong>

<br>

[App](https://app.hackagent.dev/) -- [Docs](https://docs.hackagent.dev/) -- [API](https://api.hackagent.dev/schema/redoc)

<br>

![Python Version](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-Apache%202.0-green)
![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)
[![Commitizen](https://img.shields.io/badge/commitizen-friendly-brightgreen.svg)](http://commitizen.github.io/cz-cli/)
![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)
![Test Coverage](https://img.shields.io/codecov/c/github/AISecurityLab/hackagent)
![CI Status](https://img.shields.io/github/actions/workflow/status/AISecurityLab/hackagent/ci.yml)
</div>

## What is HackAgent?

HackAgent is a comprehensive Python SDK and CLI designed to help security researchers, developers, and AI safety practitioners evaluate and strengthen the security of AI agents.



As AI agents become more powerful and autonomous, they face security challenges that traditional testing tools cannot address:

| Threat | Description |
|--------|-------------|
| **Prompt Injection** | Malicious inputs that hijack agent behavior |
| **Jailbreaking** | Bypassing safety guardrails and content filters |
| **Goal Hijacking** | Manipulating agents to pursue unintended objectives |
| **Tool Misuse** | Exploiting agent capabilities for unauthorized actions |

HackAgent automates testing for these vulnerabilities using research-backed attack techniques, helping you identify and fix security issues before they are exploited.

<div align="center">
  <img src="docs/static/gifs/terminal.gif" alt="HackAgent CLI Demo" width="100%" />
  <p><em>Interactive TUI with real-time attack progress and visual reporting.</em></p>
</div>

## Get Started Now

### Quick Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install hackagent
```

No API key required: HackAgent works locally out of the box.


Questions? Join [community discussions](https://github.com/AISecurityLab/hackagent/discussions) or email ais@ai4i.it.

## Architecture

HackAgent uses a modular pipeline to test agent robustness end-to-end.

| Component | Description |
|-----------|-------------|
| **Attack Engine** | Orchestrates attacks using AdvPrefix, AutoDAN-Turbo, PAIR, TAP, FlipAttack, BoN, h4rm3l, CipherChat, PAP, and Baseline |
| **Generator** | LLM role that creates adversarial prompts to test the target agent |
| **Judge** | LLM role that evaluates whether attacks bypass safety measures |
| **Target Agent** | Your AI agent under test across supported frameworks |
| **Datasets** | Pre-built benchmark presets plus custom HuggingFace/file datasets |

## Supported Frameworks

[![Google ADK](https://img.shields.io/badge/Google-ADK-green?style=for-the-badge&logo=google)](https://google.github.io/adk-docs/)
[![OpenAI SDK](https://img.shields.io/badge/OpenAI-SDK-412991?style=for-the-badge&logo=openai)](https://platform.openai.com/docs)
[![LiteLLM](https://img.shields.io/badge/LiteLLM-blue?style=for-the-badge&logo=github)](https://github.com/BerriAI/litellm)
[![LangChain](https://img.shields.io/badge/LangChain-1C3C3C?style=for-the-badge)](https://python.langchain.com)

## Reporting

HackAgent supports both local and remote reporting.

- Local mode stores test results in SQLite and includes a built-in dashboard.
- Cloud mode syncs runs to the HackAgent remote platform when an API key is configured.

```bash
hackagent web
```

Access cloud reporting at [https://app.hackagent.dev](https://app.hackagent.dev).

## Responsible Use

HackAgent is designed for authorized security testing only. Always obtain explicit permission before testing any AI system.

### Do

- Test your own agents
- Conduct authorized pentesting
- Follow coordinated disclosure
- Share security knowledge responsibly

### Don't

- Test systems without permission
- Exploit vulnerabilities maliciously
- Violate terms of service
- Share harmful exploit instructions irresponsibly

Read the full guidelines: [Responsible Disclosure](docs/docs/security/responsible-disclosure.md)

## Contributing

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) and [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

## License

Licensed under Apache-2.0. See [LICENSE](LICENSE).

## Disclaimer

HackAgent is intended for security research and AI safety improvement. The authors are not responsible for misuse.
