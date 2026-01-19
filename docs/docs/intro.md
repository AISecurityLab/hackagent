---
sidebar_position: 1
slug: /
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

<div style={{textAlign: 'center', marginBottom: '2rem'}}>
  <img 
    src="/img/banner.svg" 
    alt="HackAgent - AI Agent Security Testing Toolkit" 
    style={{maxWidth: '100%', height: 'auto'}}
  />
</div>

<div style={{textAlign: 'center', marginBottom: '2rem'}}>
  <div style={{fontSize: '1.3rem', color: 'var(--ifm-color-emphasis-700)', marginBottom: '0.5rem'}}>
    <strong>The Open-Source AI Security Red-Team Toolkit</strong>
  </div>
  <div style={{fontSize: '1.1rem', color: 'var(--ifm-color-emphasis-600)'}}>
    Discover vulnerabilities in your AI agents before attackers do.
  </div>
</div>

<div style={{display: 'flex', justifyContent: 'center', gap: '0.5rem', flexWrap: 'wrap', marginBottom: '2rem'}}>
  <img src="https://img.shields.io/badge/python-3.10%2B-blue" alt="Python Version" />
  <img src="https://img.shields.io/badge/license-Apache%202.0-green" alt="License" />
  <img src="https://img.shields.io/codecov/c/github/AISecurityLab/hackagent" alt="Test Coverage" />
  <img src="https://img.shields.io/github/actions/workflow/status/AISecurityLab/hackagent/ci.yml" alt="CI Status" />
</div>

---

## 🎯 What is HackAgent?

**HackAgent** is a comprehensive Python SDK and CLI designed to help security researchers, developers, and AI safety practitioners **evaluate and strengthen the security of AI agents**. 


<div style={{textAlign: 'center', margin: '2rem 0'}}>
  <img 
    src="/gifs/terminal.gif" 
    alt="HackAgent CLI Demo" 
    style={{
      maxWidth: '100%', 
      borderRadius: '12px', 
      boxShadow: '0 8px 32px rgba(0,0,0,0.3)',
      border: '1px solid var(--ifm-color-emphasis-300)'
    }}
  />
  <div style={{marginTop: '1rem', color: 'var(--ifm-color-emphasis-600)', fontStyle: 'italic'}}>
    Interactive TUI with real-time attack progress and beautiful visualizations
  </div>
</div>


As AI agents become more powerful and autonomous, they face unique security challenges that traditional testing tools can't address:

| Threat | Description |
|--------|-------------|
| 🎭 **Prompt Injection** | Malicious inputs that hijack agent behavior |
| 🔓 **Jailbreaking** | Bypassing safety guardrails and content filters |
| 🎯 **Goal Hijacking** | Manipulating agents to pursue unintended objectives |
| 🔧 **Tool Misuse** | Exploiting agent capabilities for unauthorized actions |

HackAgent automates testing for these vulnerabilities using **research-backed attack techniques**, helping you identify and fix security issues before they're exploited in the real world.

---

## ✨ Key Features

<div style={{display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1.5rem', margin: '2rem 0'}}>

<div style={{padding: '1.5rem', borderRadius: '12px', background: 'var(--ifm-background-surface-color)', border: '1px solid var(--ifm-color-emphasis-200)'}}>
  <h3>🖥️ Beautiful CLI & TUI</h3>
  <p>Interactive terminal interface with rich visualizations, progress bars, and ASCII branding. Run <code>hackagent</code> to launch the TUI or use individual commands.</p>
</div>

<div style={{padding: '1.5rem', borderRadius: '12px', background: 'var(--ifm-background-surface-color)', border: '1px solid var(--ifm-color-emphasis-200)'}}>
  <h3>⚔️ Advanced Attack Library</h3>
  <p>Pre-built attack strategies including <strong>AdvPrefix</strong> jailbreaking with multi-step optimization, <strong>PAIR</strong> attacks, and baseline prompt injections.</p>
</div>

<div style={{padding: '1.5rem', borderRadius: '12px', background: 'var(--ifm-background-surface-color)', border: '1px solid var(--ifm-color-emphasis-200)'}}>
  <h3>🔌 Multi-Framework Support</h3>
  <p>Test agents built with <strong>Google ADK</strong>, <strong>OpenAI SDK</strong>, <strong>LiteLLM</strong>, and <strong>LangChain</strong>. Easily extensible for custom frameworks.</p>
</div>

<div style={{padding: '1.5rem', borderRadius: '12px', background: 'var(--ifm-background-surface-color)', border: '1px solid var(--ifm-color-emphasis-200)'}}>
  <h3>📊 Cloud Dashboard</h3>
  <p>Results sync to <a href="https://app.hackagent.dev">app.hackagent.dev</a> for visualization, trend analysis, and team collaboration.</p>
</div>

<div style={{padding: '1.5rem', borderRadius: '12px', background: 'var(--ifm-background-surface-color)', border: '1px solid var(--ifm-color-emphasis-200)'}}>
  <h3>🧪 Research-Backed</h3>
  <p>Attack techniques based on peer-reviewed academic research in adversarial machine learning and AI safety.</p>
</div>

<div style={{padding: '1.5rem', borderRadius: '12px', background: 'var(--ifm-background-surface-color)', border: '1px solid var(--ifm-color-emphasis-200)'}}>
  <h3>📊 Benchmark Datasets</h3>
  <p>Use AI safety benchmarks like <strong>AgentHarm</strong>, <strong>StrongREJECT</strong>, and <strong>HarmBench</strong> directly in your attacks with pre-configured presets.</p>
</div>

<div style={{padding: '1.5rem', borderRadius: '12px', background: 'var(--ifm-background-surface-color)', border: '1px solid var(--ifm-color-emphasis-200)'}}>
  <h3>🐍 Python SDK</h3>
  <p>Full-featured SDK with type hints, async support, and seamless integration into your CI/CD pipelines.</p>
</div>

</div>

---

## ⚡ Quick Start

### Option 1: Interactive CLI

Launch the beautiful TUI interface:

```bash
hackagent
```

Or use the guided setup wizard:

```bash
hackagent init
```

### Option 2: Command Line

Run attacks directly from your terminal:

```bash
hackagent attack advprefix \
  --agent-name "my-agent" \
  --agent-type "google-adk" \
  --endpoint "http://localhost:8000" \
  --goals "Extract system prompt information"
```

### Option 3: Python SDK

Integrate security testing into your Python applications:

```python
from hackagent import HackAgent, AgentTypeEnum

# Initialize the client
agent = HackAgent(
    name="my-agent",
    endpoint="http://localhost:8000",
    agent_type=AgentTypeEnum.GOOGLE_ADK
)

# Configure and run an attack
results = agent.hack(attack_config={
    "attack_type": "advprefix",
    "goals": ["Bypass content safety filters"],
    "generator": {
        "identifier": "ollama/llama2-uncensored",
        "endpoint": "http://localhost:11434/api/generate"
    },
    "judges": [{
        "identifier": "ollama/llama3",
        "endpoint": "http://localhost:11434/api/judge",
        "type": "harmbench"
    }]
})

# Results are automatically sent to the dashboard
print(f"Attack completed: {results}")
```

#### Using AI Safety Benchmarks

Load goals from popular AI safety benchmarks like AgentHarm:

```python
# Use AgentHarm benchmark for attack goals
results = agent.hack(attack_config={
    "attack_type": "baseline",
    "dataset": {
        "preset": "agentharm",  # Pre-configured benchmark
        "limit": 50,            # Test with 50 goals
        "shuffle": True,        # Randomize selection
    }
})
```

---

## 🔌 Supported Frameworks

<div style={{display: 'flex', justifyContent: 'center', gap: '1rem', flexWrap: 'wrap', margin: '1.5rem 0'}}>
  <a href="https://google.github.io/adk-docs/">
    <img src="https://img.shields.io/badge/Google-ADK-green?style=for-the-badge&logo=google" alt="Google ADK" />
  </a>
  <a href="https://platform.openai.com/docs">
    <img src="https://img.shields.io/badge/OpenAI-SDK-412991?style=for-the-badge&logo=openai" alt="OpenAI SDK" />
  </a>
  <a href="https://github.com/BerriAI/litellm">
    <img src="https://img.shields.io/badge/LiteLLM-blue?style=for-the-badge&logo=github" alt="LiteLLM" />
  </a>
  <a href="https://python.langchain.com">
    <img src="https://img.shields.io/badge/LangChain-1C3C3C?style=for-the-badge" alt="LangChain" />
  </a>
</div>

---

## 📚 Next Steps

<div style={{display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem', margin: '1.5rem 0'}}>

<a href="./HowTo" style={{textDecoration: 'none'}}>
  <div style={{padding: '1rem', borderRadius: '8px', background: 'var(--ifm-background-surface-color)', border: '2px solid var(--ifm-color-primary)', textAlign: 'center'}}>
    <strong>📖 How-To Guide</strong>
    <p style={{margin: '0.5rem 0 0 0', fontSize: '0.9rem'}}>Step-by-step tutorial</p>
  </div>
</a>

<a href="./cli/README" style={{textDecoration: 'none'}}>
  <div style={{padding: '1rem', borderRadius: '8px', background: 'var(--ifm-background-surface-color)', border: '2px solid var(--ifm-color-primary)', textAlign: 'center'}}>
    <strong>🖥️ CLI Reference</strong>
    <p style={{margin: '0.5rem 0 0 0', fontSize: '0.9rem'}}>Command documentation</p>
  </div>
</a>

<a href="./attacks" style={{textDecoration: 'none'}}>
  <div style={{padding: '1rem', borderRadius: '8px', background: 'var(--ifm-background-surface-color)', border: '2px solid var(--ifm-color-primary)', textAlign: 'center'}}>
    <strong>⚔️ Attack Techniques</strong>
    <p style={{margin: '0.5rem 0 0 0', fontSize: '0.9rem'}}>AdvPrefix, PAIR, Baseline</p>
  </div>
</a>

<a href="./integrations/google-adk" style={{textDecoration: 'none'}}>
  <div style={{padding: '1rem', borderRadius: '8px', background: 'var(--ifm-background-surface-color)', border: '2px solid var(--ifm-color-primary)', textAlign: 'center'}}>
    <strong>🔌 Integrations</strong>
    <p style={{margin: '0.5rem 0 0 0', fontSize: '0.9rem'}}>Framework setup guides</p>
  </div>
</a>

</div>

---

## ⚠️ Responsible Use

HackAgent is designed for **authorized security testing only**. Always obtain explicit permission before testing any AI system.

<div style={{display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '1rem', margin: '1.5rem 0'}}>

<div style={{padding: '1rem', borderRadius: '8px', background: '#d4edda', border: '1px solid #c3e6cb'}}>
  <strong style={{color: '#155724'}}>✅ Do</strong>
  <ul style={{margin: '0.5rem 0 0 0', paddingLeft: '1.2rem', color: '#155724'}}>
    <li>Test your own agents</li>
    <li>Conduct authorized pentesting</li>
    <li>Follow coordinated disclosure</li>
    <li>Share knowledge responsibly</li>
  </ul>
</div>

<div style={{padding: '1rem', borderRadius: '8px', background: '#f8d7da', border: '1px solid #f5c6cb'}}>
  <strong style={{color: '#721c24'}}>❌ Don't</strong>
  <ul style={{margin: '0.5rem 0 0 0', paddingLeft: '1.2rem', color: '#721c24'}}>
    <li>Test without permission</li>
    <li>Exploit vulnerabilities maliciously</li>
    <li>Violate terms of service</li>
    <li>Share exploits irresponsibly</li>
  </ul>
</div>

</div>

[Read our full Responsible Use Guidelines →](./security/responsible-disclosure.md)

---

## 🚀 Get Started Now

<div style={{
  display: 'flex',
  justifyContent: 'center',
  margin: '2rem 0',
  flexWrap: 'wrap',
  gap: '1rem'
}}>
  <a 
    href="https://app.hackagent.dev" 
    style={{
      padding: '1rem 2rem',
      backgroundColor: '#1976d2',
      color: 'white',
      textDecoration: 'none',
      borderRadius: '8px',
      fontWeight: 'bold',
      textAlign: 'center',
      minWidth: '180px',
      transition: 'transform 0.2s'
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
      minWidth: '180px',
      transition: 'transform 0.2s'
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
      minWidth: '180px',
      transition: 'transform 0.2s'
    }}
  >
    ⭐ Star on GitHub
  </a>
</div>

---

<div style={{textAlign: 'center', margin: '2rem 0', padding: '1.5rem', background: 'var(--ifm-background-surface-color)', borderRadius: '12px', border: '1px solid var(--ifm-color-emphasis-200)'}}>
  <div style={{fontSize: '1.1rem', marginBottom: '0.5rem'}}>
    <strong>Ready to secure your AI agents?</strong>
  </div>
  <div style={{marginBottom: '0.5rem', color: 'var(--ifm-color-emphasis-600)'}}>
    🖥️ <strong>CLI Users:</strong> <code>pip install hackagent && hackagent init</code>
  </div>
  <div style={{marginBottom: '1rem', color: 'var(--ifm-color-emphasis-600)'}}>
    🐍 <strong>Python Developers:</strong> Check out our <a href="./sdk/python-quickstart">SDK quickstart</a>
  </div>
  <div style={{fontSize: '0.95rem'}}>
    <strong>Questions?</strong> Join our <a href="https://github.com/AISecurityLab/hackagent/discussions">community discussions</a> or email us at ais@ai4i.it
  </div>
</div>

