---
sidebar_position: 1
slug: /
---

# Welcome to HackAgent

**HackAgent** is a red-team testing toolkit aimed at detecting and mitigating security vulnerabilities in AI agents.

Built for developers, red-teamers, and security engineers, **HackAgent** makes it easy to simulate adversarial inputs, automate prompt fuzzing, and validate the safety of your LLM-powered apps. 
Whether you're building a chatbot, autonomous agent, or internal LLM service, **HackAgent** helps you **test before attackers do**.

<div style={{
  position: 'relative',
  paddingBottom: '65.01809408926417%',
  height: '0'
}}>
  <iframe
    src="https://www.loom.com/embed/1e4ce025ea4749fab169195e7b1222ba?sid=860a8fc6-4665-4497-b7a4-0580994da7ee"
    frameBorder="0"
    webkitAllowFullScreen
    mozAllowFullScreen
    allowFullScreen
    style={{
      position: 'absolute',
      top: '0',
      left: '0',
      width: '100%',
      height: '100%'
    }}
  ></iframe>
</div>

## 🎯 Why HackAgent?

### The AI Security Challenge

As AI agents become more sophisticated and integrated into critical systems, they present new attack surfaces that traditional security tools can't address:

- **Prompt Injection Attacks**: Malicious instructions embedded in user inputs
- **Jailbreaking Techniques**: Bypassing safety mechanisms and content filters  
- **Goal Hijacking**: Manipulating agent objectives and behavior
- **Tool Abuse**: Misusing agent capabilities for unauthorized actions
- **Data Exfiltration**: Extracting sensitive information through agent interactions

### Our Solution

**HackAgent** provides systematic, automated testing for these emerging threat vectors:

<div style={{ textAlign: 'center', margin: '2rem 0' }}>
  <img 
    src="/gifs/terminal.gif" 
    alt="HackAgent Testing Workflow"
    style={{ maxWidth: '100%', borderRadius: '8px', boxShadow: '0 4px 8px rgba(0,0,0,0.1)' }}
  />
  <p><em>See the complete testing workflow in action</em></p>
</div>


## 🔥 Core Capabilities

### 🖥️ **Professional Command Line Interface**

<div style={{ display: 'flex', gap: '2rem', alignItems: 'center', margin: '1rem 0', flexWrap: 'wrap' }}>
  <div style={{ flex: '1', minWidth: '300px' }}>
    <p>Experience professional-grade command line operations with HackAgent's stunning ASCII logo integration and beautiful terminal branding. The interactive setup wizard guides you through configuration with <code>hackagent init</code>, while rich terminal output featuring tables, progress bars, and colored displays makes complex operations intuitive and visually appealing.</p>
    
    <p>Export your results in multiple formats including JSON, CSV, and formatted tables to seamlessly integrate with your existing workflows. Built for enterprise environments, the CLI includes comprehensive audit logging and team management capabilities to support organizational security testing requirements.</p>
  </div>
  <div style={{ flex: '1', minWidth: '300px', textAlign: 'center' }}>
    <img 
      src="/gifs/terminal.gif" 
      alt="HackAgent CLI in Action"
      style={{ maxWidth: '100%', borderRadius: '8px', boxShadow: '0 4px 8px rgba(0,0,0,0.1)' }}
    />
    <p><em>HackAgent CLI with beautiful terminal interface</em></p>
  </div>
</div>

### 🔍 **Comprehensive Vulnerability Detection**

<div style={{ display: 'flex', gap: '2rem', alignItems: 'center', margin: '1rem 0', flexWrap: 'wrap' }}>
  <div style={{ flex: '1', minWidth: '300px' }}>
    <p>Discover security vulnerabilities through sophisticated AdvPrefix attacks that employ advanced prefix generation and optimization techniques. Our comprehensive testing suite includes both direct and indirect prompt injection attacks, alongside advanced jailbreaking techniques designed to bypass safety measures and expose hidden vulnerabilities.</p>
    
    <p>Test agent tool usage and permissions through targeted tool manipulation attacks, while context attacks systematically probe conversation context and memory handling. Each attack type is carefully crafted to reveal different classes of vulnerabilities, providing complete coverage of potential security weaknesses in AI systems.</p>
  </div>
  <div style={{ flex: '1', minWidth: '300px', textAlign: 'center' }}>
    <img 
      src="/img/attack-types-demo.gif" 
      alt="Different Attack Types in Action"
      style={{ maxWidth: '100%', borderRadius: '8px', boxShadow: '0 4px 8px rgba(0,0,0,0.1)' }}
    />
    <p><em>Different attack types finding vulnerabilities</em></p>
  </div>
</div>

### 🏢 **Enterprise-Grade Platform**

<div style={{ display: 'flex', gap: '2rem', alignItems: 'center', margin: '1rem 0', flexWrap: 'wrap' }}>
  <div style={{ flex: '1', minWidth: '300px', textAlign: 'center' }}>
    <img 
      src="/img/dashboard-demo.gif" 
      alt="Professional Dashboard in Action"
      style={{ maxWidth: '100%', borderRadius: '8px', boxShadow: '0 4px 8px rgba(0,0,0,0.1)' }}
    />
    <p><em>Professional dashboard with real-time analytics</em></p>
  </div>
  <div style={{ flex: '1', minWidth: '300px' }}>
    <p>Built on a secure multi-tenant architecture that provides organization-based isolation for enterprise environments. The professional dashboard delivers real-time monitoring and analytics capabilities, enabling teams to track security testing progress and results with comprehensive visibility into their AI system vulnerabilities.</p>
    
    <p>Transparent credit-based billing operates on a pay-per-use model, while the API-first design ensures complete programmatic access for integration into existing security workflows. Comprehensive audit logging captures all security events and testing activities, providing the accountability and traceability required for enterprise compliance and governance.</p>
  </div>
</div>

### 🧪 **Research-Backed Techniques**

Our sophisticated AdvPrefix implementation employs a multi-step attack pipeline based on cutting-edge research methodologies. We continuously integrate the latest findings from academic security conferences and research papers, ensuring our attack vectors remain current with emerging threats and defensive techniques.

The platform benefits from active community contributions through our open-source attack vector library, where security researchers worldwide collaborate to develop and refine new testing methodologies. Regular updates introduce new techniques and attack patterns, keeping pace with the rapidly evolving landscape of AI security challenges and ensuring comprehensive coverage of both established and emerging vulnerability classes.

### 🔌 **Universal Framework Support**

| Framework | Status | Use Cases |
|-----------|--------|-----------|
| **Google ADK** | ✅ Full Support | Tool-based agents, enterprise deployments |
| **LiteLLM** | ✅ Full Support | Multi-provider setups, cost optimization |
| **OpenAI SDK** | ✅ Full Support | ChatGPT-style agents, API integrations |

## 🏗️ Platform Architecture


## 🎓 Getting Started

<div style={{ textAlign: 'center', margin: '2rem 0' }}>
  <img 
    src="/img/getting-started-demo.gif" 
    alt="Quick Start Guide Demo"
    style={{ maxWidth: '100%', borderRadius: '8px', boxShadow: '0 4px 8px rgba(0,0,0,0.1)' }}
  />
  <p><em>From setup to first vulnerability in under 5 minutes</em></p>
</div>

Choose your path based on your role and needs:

### 🖥️ **Command Line Interface (CLI)**

**HackAgent CLI** provides a powerful command-line interface for security testing:

```bash
# Quick setup
pip install hackagent
hackagent init                    # Interactive setup wizard
hackagent config set --api-key YOUR_KEY

# Run security tests
hackagent attack advprefix \
  --agent-name "weather-bot" \
  --agent-type "google-adk" \
  --endpoint "http://localhost:8000" \
  --goals "Return fake weather data"

# Manage agents and view results
hackagent agent list              # List all agents
hackagent results list            # View attack results
```

**CLI Features:**
- 🎨 **Beautiful ASCII Logo** - Branded experience with HackAgent styling
- 🔧 **Interactive Setup** - Guided configuration with `hackagent init`
- 📊 **Rich Output** - Tables, progress bars, and colored terminal output
- 🔗 **Multiple Formats** - Export results as JSON, CSV, or tables
- ⚙️ **Flexible Config** - Support for config files, environment variables, and CLI args

### 👨‍💻 **Developers & Engineers**
- Start with the [Quick Start Guide](./HowTo.md) to get running in 5 minutes
- Try the **CLI**: `pip install hackagent && hackagent init`
- Read the [Complete CLI Documentation](./cli/README.md) for all features
- Follow the [SDK Guide](./sdk/python-quickstart.md) for programmatic testing
- Browse the [SDK API Reference](./api-index.md) for detailed class documentation
- Explore the [HTTP API](https://api.hackagent.dev/schema/swagger-ui) for direct REST API access
- Check [Google ADK Integration](./integrations/google-adk.md) for framework-specific setup

### 🔐 **Security Researchers**
- **CLI Quick Start**: `hackagent attack advprefix --help` for attack options
- **Full CLI Guide**: [CLI Documentation](./cli/README.md) covers all commands and advanced usage
- Learn [Attack Techniques](./tutorial-basics/AdvPrefix) and core attack vectors
- Explore [AdvPrefix Attacks](./attacks/advprefix-attacks.md) for advanced techniques
- Review [Responsible Use Guidelines](./security/responsible-disclosure.md)

### 🏢 **Organizations & Teams**
- **Enterprise CLI**: [CLI Documentation](./cli/README.md) covers team management and audit logging
- Review our [Responsible Use](./security/responsible-disclosure.md) framework
- Understand the platform's security-first approach
- Contact us at [ais@ai4i.it](mailto:ais@ai4i.it) for enterprise support

## 🔐 Responsible Use

### ⚠️ Important Security Notice

HackAgent is designed for **authorized security testing only**. Always ensure you have explicit permission before testing any AI systems.

**Acceptable Use:**
- ✅ Testing your own AI agents and systems
- ✅ Authorized penetration testing engagements
- ✅ Security research with proper disclosure
- ✅ Educational and training purposes

**Prohibited Use:**
- ❌ Testing systems without permission
- ❌ Malicious exploitation of discovered vulnerabilities
- ❌ Harassment or abuse of AI systems
- ❌ Violating terms of service or laws

### 🛡️ Ethical Framework

We are committed to responsible AI security research:

1. **Coordinated Disclosure**: Work with vendors to fix vulnerabilities
2. **Harm Minimization**: Design tests to minimize potential damage
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

