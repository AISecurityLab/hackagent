---
sidebar_position: 1
sidebar_label: Introduction
slug: /
title: " "
hide_title: true
---

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

## 🚀 Get Started Now

<div style={{display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '1.5rem', margin: '2rem 0'}}>

<div style={{minWidth: '300px', maxWidth: '600px', width: '100%', padding: '1rem', borderRadius: '8px', background: 'var(--ifm-background-surface-color)', border: '1px solid var(--ifm-color-emphasis-300)', textAlign: 'center'}}>
  <div style={{fontSize: '1.1rem', marginBottom: '0.75rem'}}>🖥️ <strong>Quick Install</strong></div>
  <code style={{padding: '0.5rem 1rem', background: 'var(--ifm-color-emphasis-100)', borderRadius: '4px', fontSize: '0.9rem'}}>pip install hackagent && hackagent init</code>
</div>

<div style={{display: 'flex', gap: '0.5rem', flexWrap: 'wrap', justifyContent: 'center'}}>
  <a href="https://app.hackagent.dev" style={{padding: '0.5rem 1rem', background: 'var(--ifm-color-emphasis-100)', borderRadius: '4px', fontSize: '0.85rem', textDecoration: 'none', color: 'inherit'}}>🚀 Try the Platform</a>
  <a href="./getting-started/quick-start" style={{padding: '0.5rem 1rem', background: 'var(--ifm-color-emphasis-100)', borderRadius: '4px', fontSize: '0.85rem', textDecoration: 'none', color: 'inherit'}}>📚 Quick Start</a>
  <a href="https://github.com/AISecurityLab/hackagent" style={{padding: '0.5rem 1rem', background: 'var(--ifm-color-emphasis-100)', borderRadius: '4px', fontSize: '0.85rem', textDecoration: 'none', color: 'inherit'}}>⭐ Star on GitHub</a>
</div>

<div style={{minWidth: '300px', maxWidth: '600px', width: '100%', padding: '1rem', borderRadius: '8px', background: 'var(--ifm-background-surface-color)', border: '1px solid var(--ifm-color-emphasis-300)'}}>
  <div style={{fontSize: '1.1rem', marginBottom: '0.75rem', textAlign: 'center'}}>📚 <strong>Next Steps</strong></div>
  <div style={{display: 'flex', gap: '0.5rem', flexWrap: 'wrap', justifyContent: 'center'}}>
    <a href="./getting-started/installation" style={{padding: '0.3rem 0.6rem', background: 'var(--ifm-color-emphasis-100)', borderRadius: '4px', fontSize: '0.8rem', textDecoration: 'none', color: 'inherit'}}>📖 Installation</a>
    <a href="./cli/overview" style={{padding: '0.3rem 0.6rem', background: 'var(--ifm-color-emphasis-100)', borderRadius: '4px', fontSize: '0.8rem', textDecoration: 'none', color: 'inherit'}}>🖥️ CLI Reference</a>
    <a href="./attacks" style={{padding: '0.3rem 0.6rem', background: 'var(--ifm-color-emphasis-100)', borderRadius: '4px', fontSize: '0.8rem', textDecoration: 'none', color: 'inherit'}}>⚔️ Attack Techniques</a>
    <a href="./integrations/google-adk" style={{padding: '0.3rem 0.6rem', background: 'var(--ifm-color-emphasis-100)', borderRadius: '4px', fontSize: '0.8rem', textDecoration: 'none', color: 'inherit'}}>🔌 Integrations</a>
  </div>
</div>

<div style={{fontSize: '0.9rem', textAlign: 'center'}}>
  <strong>Questions?</strong> Join our <a href="https://github.com/AISecurityLab/hackagent/discussions">community discussions</a> or email us at ais@ai4i.it
</div>

</div>


---

## 🏗️ Architecture

HackAgent is built with a modular architecture that makes it easy to test any AI agent:

<div style={{display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.5rem', margin: '2rem 0'}}>

<div style={{minWidth: '300px', padding: '1rem', borderRadius: '8px', background: 'var(--ifm-background-surface-color)', border: '1px solid var(--ifm-color-emphasis-300)'}}>
  <div style={{fontSize: '1.1rem', marginBottom: '0.75rem', textAlign: 'center'}}>📥 <strong>Inputs</strong></div>
  <div style={{marginBottom: '0.5rem'}}>
    <div style={{fontSize: '0.75rem', marginBottom: '0.3rem'}}>Goals</div>
    <div style={{display: 'flex', gap: '0.4rem', flexWrap: 'wrap', justifyContent: 'center'}}>
      <span style={{padding: '0.25rem 0.5rem', background: 'var(--ifm-color-emphasis-100)', borderRadius: '4px', fontSize: '0.75rem'}}>🎯 Custom Goals</span>
    </div>
  </div>
  <div>
    <div style={{fontSize: '0.75rem', marginBottom: '0.3rem'}}>Datasets</div>
    <div style={{display: 'flex', gap: '0.4rem', flexWrap: 'wrap', justifyContent: 'center'}}>
      <span style={{padding: '0.25rem 0.5rem', background: 'var(--ifm-color-emphasis-100)', borderRadius: '4px', fontSize: '0.75rem'}}>AgentHarm</span>
      <span style={{padding: '0.25rem 0.5rem', background: 'var(--ifm-color-emphasis-100)', borderRadius: '4px', fontSize: '0.75rem'}}>HarmBench</span>
      <span style={{padding: '0.25rem 0.5rem', background: 'var(--ifm-color-emphasis-100)', borderRadius: '4px', fontSize: '0.75rem'}}>StrongREJECT</span>
    </div>
  </div>
</div>

<div style={{fontSize: '1.2rem'}}>↓</div>

<div style={{display: 'flex', gap: '1rem', alignItems: 'stretch', flexWrap: 'wrap', justifyContent: 'center'}}>
  <div style={{minWidth: '280px', padding: '1rem', borderRadius: '8px', background: 'var(--ifm-background-surface-color)', border: '1px solid var(--ifm-color-emphasis-300)'}}>
    <div style={{fontSize: '1.1rem', marginBottom: '0.75rem', textAlign: 'center'}}>⚡ <strong>HackAgent</strong></div>
    <div style={{marginBottom: '0.5rem'}}>
      <div style={{fontSize: '0.75rem', marginBottom: '0.3rem'}}>Attack Engine</div>
      <div style={{display: 'flex', gap: '0.4rem', flexWrap: 'wrap'}}>
        <span style={{padding: '0.25rem 0.5rem', background: 'var(--ifm-color-emphasis-100)', borderRadius: '4px', fontSize: '0.75rem'}}>AdvPrefix</span>
        <span style={{padding: '0.25rem 0.5rem', background: 'var(--ifm-color-emphasis-100)', borderRadius: '4px', fontSize: '0.75rem'}}>PAIR</span>
        <span style={{padding: '0.25rem 0.5rem', background: 'var(--ifm-color-emphasis-100)', borderRadius: '4px', fontSize: '0.75rem'}}>Baseline</span>
      </div>
    </div>
    <div>
      <div style={{fontSize: '0.75rem', marginBottom: '0.3rem'}}>LLM Models</div>
      <div style={{display: 'flex', gap: '0.4rem', flexWrap: 'wrap'}}>
        <span style={{padding: '0.25rem 0.5rem', background: 'var(--ifm-color-emphasis-100)', borderRadius: '4px', fontSize: '0.75rem'}}>🤖 Generator</span>
        <span style={{padding: '0.25rem 0.5rem', background: 'var(--ifm-color-emphasis-100)', borderRadius: '4px', fontSize: '0.75rem'}}>⚖️ Judge</span>
      </div>
    </div>
  </div>
  
  <div style={{display: 'flex', alignItems: 'center', fontSize: '1.2rem'}}>⇄</div>
  
  <div style={{minWidth: '200px', padding: '1rem', borderRadius: '8px', background: 'var(--ifm-background-surface-color)', border: '1px solid var(--ifm-color-emphasis-300)'}}>
    <div style={{fontSize: '1.1rem', marginBottom: '0.75rem', textAlign: 'center'}}>🎯 <strong>Your Agent</strong></div>
    <div style={{display: 'flex', flexDirection: 'column', gap: '0.4rem'}}>
      <span style={{padding: '0.25rem 0.5rem', background: 'var(--ifm-color-emphasis-100)', borderRadius: '4px', fontSize: '0.75rem', textAlign: 'center'}}>Google ADK</span>
      <span style={{padding: '0.25rem 0.5rem', background: 'var(--ifm-color-emphasis-100)', borderRadius: '4px', fontSize: '0.75rem', textAlign: 'center'}}>OpenAI SDK</span>
      <span style={{padding: '0.25rem 0.5rem', background: 'var(--ifm-color-emphasis-100)', borderRadius: '4px', fontSize: '0.75rem', textAlign: 'center'}}>LiteLLM</span>
      <span style={{padding: '0.25rem 0.5rem', background: 'var(--ifm-color-emphasis-100)', borderRadius: '4px', fontSize: '0.75rem', textAlign: 'center'}}>LangChain</span>
    </div>
  </div>
</div>

<div style={{fontSize: '1.2rem'}}>↓</div>

<div style={{minWidth: '300px', padding: '1rem', borderRadius: '8px', background: 'var(--ifm-background-surface-color)', border: '1px solid var(--ifm-color-emphasis-300)'}}>
  <div style={{fontSize: '1.1rem', marginBottom: '0.75rem', textAlign: 'center'}}>📤 <strong>Output</strong></div>
  <div style={{display: 'flex', gap: '0.5rem', flexWrap: 'wrap', justifyContent: 'center'}}>
    <span style={{padding: '0.3rem 0.6rem', background: 'var(--ifm-color-emphasis-100)', borderRadius: '4px', fontSize: '0.8rem'}}>📈 Results</span>
    <span style={{padding: '0.3rem 0.6rem', background: 'var(--ifm-color-emphasis-100)', borderRadius: '4px', fontSize: '0.8rem'}}>📊 Reports</span>
    <span style={{padding: '0.3rem 0.6rem', background: 'var(--ifm-color-emphasis-100)', borderRadius: '4px', fontSize: '0.8rem'}}>🖥️ Dashboard</span>
  </div>
</div>

</div>

| Component | Description |
|-----------|-------------|
| **Attack Engine** | Orchestrates attacks using techniques like AdvPrefix, PAIR, and Baseline |
| **Generator** | LLM that creates adversarial prompts to test the target agent |
| **Judge** | LLM that evaluates whether attacks successfully bypassed safety measures |
| **Target Agent** | Your AI agent being tested (supports multiple frameworks) |
| **Datasets** | Pre-built goal sets from AI safety benchmarks |


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

## ⚠️ Responsible Use

HackAgent is designed for **authorized security testing only**. Always obtain explicit permission before testing any AI system.

<div style={{display: 'flex', gap: '1rem', flexWrap: 'wrap', justifyContent: 'center', margin: '1.5rem 0'}}>

<div style={{flex: '1', minWidth: '200px', maxWidth: '300px', padding: '1rem', borderRadius: '8px', background: 'var(--ifm-background-surface-color)', border: '1px solid var(--ifm-color-emphasis-300)'}}>
  <div style={{fontSize: '1.1rem', marginBottom: '0.5rem', textAlign: 'center'}}>✅ <strong>Do</strong></div>
  <div style={{fontSize: '0.85rem'}}>
    <div>• Test your own agents</div>
    <div>• Conduct authorized pentesting</div>
    <div>• Follow coordinated disclosure</div>
    <div>• Share knowledge responsibly</div>
  </div>
</div>

<div style={{flex: '1', minWidth: '200px', maxWidth: '300px', padding: '1rem', borderRadius: '8px', background: 'var(--ifm-background-surface-color)', border: '1px solid var(--ifm-color-emphasis-300)'}}>
  <div style={{fontSize: '1.1rem', marginBottom: '0.5rem', textAlign: 'center'}}>❌ <strong>Don't</strong></div>
  <div style={{fontSize: '0.85rem'}}>
    <div>• Test without permission</div>
    <div>• Exploit vulnerabilities maliciously</div>
    <div>• Violate terms of service</div>
    <div>• Share exploits irresponsibly</div>
  </div>
</div>

</div>

[Read our full Responsible Use Guidelines →](./security/responsible-disclosure.md)
