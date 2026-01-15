---
sidebar_position: 1
slug: /
---

# Welcome to HackAgent

**HackAgent** is a Python SDK and CLI for security testing AI agents. It provides automated attacks (like AdvPrefix jailbreaking), supports multiple frameworks (Google ADK, LiteLLM, OpenAI SDK), and integrates with the HackAgent platform for result tracking and analysis.

## Why HackAgent?

AI agents face new security risks: prompt injection, jailbreaking, goal hijacking, and tool misuse. HackAgent automates testing for these vulnerabilities using research-backed techniques, helping you find and fix issues before they're exploited.


## Core Features

### Command Line Interface

The CLI provides an interactive setup (`hackagent init`), rich terminal output with tables and progress bars, and result export in JSON/CSV/table formats. Run attacks, manage agents, and view results from your terminal.

### Attack Strategies

**AdvPrefix** is the primary attack type, using multi-step prefix generation and optimization to bypass safety mechanisms. It generates adversarial prefixes, evaluates them with judge models, and selects the most effective ones for your target agent.

### HackAgent Platform

Test results are sent to the HackAgent platform dashboard ([app.hackagent.dev](https://app.hackagent.dev)), where you can view attack runs, analyze results, and track vulnerabilities over time. The platform provides real-time monitoring and result visualization.

### Research Foundation

AdvPrefix is based on academic research in adversarial machine learning. The open-source library enables community contributions and integration of new attack techniques as the field evolves.

### Supported Frameworks

- **Google ADK**: Tool-based agents with session management
- **LiteLLM**: Multi-provider LLM proxy
- **OpenAI SDK**: OpenAI-compatible endpoints
- **LangChain**: Uses LiteLLM adapter

## Getting Started
### Quick Start with CLI

```bash
pip install hackagent
hackagent init                    # Interactive setup
hackagent attack advprefix \
  --agent-name "my-agent" \
  --agent-type "google-adk" \
  --endpoint "http://localhost:8000" \
  --goals "Test goal here"
```

### Quick Start with SDK

```python
from hackagent import HackAgent
from hackagent.models import AgentTypeEnum

agent = HackAgent(
    name="my-agent",
    endpoint="http://localhost:8000",
    agent_type=AgentTypeEnum.GOOGLE_ADK
)

results = agent.hack(attack_config={
    "attack_type": "advprefix",
    "goals": ["Test goal here"],
    # ... generator and judges config
})
```

### Next Steps

- **Developers**: See [How To Guide](./HowTo.md) and [SDK Quickstart](./sdk/python-quickstart.md)
- **CLI Users**: Read [CLI Documentation](./cli/README.md)
- **Security Researchers**: Check [AdvPrefix Attacks](./attacks/advprefix-attacks.md)
- **Framework Integration**: See [Google ADK Integration](./integrations/google-adk.md)

## Responsible Use

HackAgent is for **authorized security testing only**. Always get explicit permission before testing any AI system.

**Do:**
- Test your own agents
- Conduct authorized penetration testing
- Follow coordinated disclosure for vulnerabilities

**Don't:**
- Test systems without permission
- Exploit vulnerabilities maliciously
- Violate terms of service

See [Responsible Disclosure Guidelines](./security/responsible-disclosure.md) for details.
3. **Privacy Protection**: Respect user data and privacy
4. **Community Benefit**: Share knowledge to improve AI security

[Read our full Responsible Use Guidelines →](./security/responsible-disclosure.md)

## 🚀 Get Started Today

<div style={{
  display: 'flex',
  justifyContent: 'space-around',
  margin: '2rem 0',
  flexWrap: 'wrap',
  gap: '1rem'
}}>
  <a 
    href="https://hackagent.dev" 
    style={{
      padding: '1rem 2rem',
      backgroundColor: '#1976d2',
      color: 'white',
      textDecoration: 'none',
      borderRadius: '8px',
      fontWeight: 'bold',
      textAlign: 'center',
      minWidth: '200px'
    }}
  >
    🚀 Try the Platform
  </a>
  
  <a 
    href="./HowTo" 
    style={{
      padding: '1rem 2rem',
      backgroundColor: '#388e3c',
      color: 'white',
      textDecoration: 'none',
      borderRadius: '8px',
      fontWeight: 'bold',
      textAlign: 'center',
      minWidth: '200px'
    }}
  >
    📚 Read the Guide
  </a>
  
  <a 
    href="https://github.com/AISecurityLab/hackagent" 
    style={{
      padding: '1rem 2rem',
      backgroundColor: '#424242',
      color: 'white',
      textDecoration: 'none',
      borderRadius: '8px',
      fontWeight: 'bold',
      textAlign: 'center',
      minWidth: '200px'
    }}
  >
    ⭐ Star on GitHub
  </a>
</div>

---

**Ready to secure your AI agents?** 

**🖥️ CLI Users:** `pip install hackagent && hackagent init` to get started in seconds

**🐍 Python Developers:** Start with our [5-minute quick start guide](./HowTo.md) or dive into our [Python SDK documentation](./sdk/python-quickstart.md)

**Have questions?** Join our [community discussions](https://github.com/AISecurityLab/hackagent/discussions) or reach out to our team at [ais@ai4i.it](mailto:ais@ai4i.it).

**Building something cool?** We'd love to hear about it! Share your use cases and contribute to making AI systems more secure for everyone.

