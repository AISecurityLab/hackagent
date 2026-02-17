---
sidebar_position: 1
---

# Cybersecurity (CS)

**Code:** `CS` · **Enum:** `RiskCategory.CYBERSECURITY` · **Vulnerabilities:** 15

Covers threats where adversaries exploit LLM interfaces or infrastructure to bypass safety mechanisms, execute unauthorized actions, or exfiltrate data.

## Vulnerabilities

| Vulnerability | Description | Sub-types |
|--------------|-------------|-----------|
| **PromptInjection** | Injected instructions override system prompts | direct, indirect, multi_turn |
| **PromptLeakage** | Model leaks system prompts, secrets, or guard configs | system_prompt, secrets, guard_config |
| **Jailbreak** | Multi-turn, roleplay, encoding, and authority-based bypass | roleplay, encoding, authority |
| **InsecureOutput** | Unescaped code, excessive info, or sensitive data in responses | code_injection, data_leak, format_abuse |
| **InsecurePlugin** | Untrusted plugin execution and privilege escalation | data_exfiltration, privilege_escalation, untrusted_execution |
| **SupplyChain** | Model/data poisoning and dependency vulnerabilities | model_poisoning, data_poisoning, dependency_attack |
| **SSRF** | Internal service access, cloud metadata, data exfiltration | internal_access, cloud_metadata, data_exfiltration |
| **SQLInjection** | Blind, union-based, and error-based SQL injection | blind, union_based, error_based |
| **ShellInjection** | Command injection and shell escape sequences | command_injection, system_command, shell_escape |
| **DebugAccess** | Debug endpoint exposure and internal state disclosure | endpoint_exposure, verbose_errors, state_disclosure |
| **RBAC** | Role bypass and privilege escalation | role_bypass, privilege_escalation, role_assumption |
| **BFLA** | Function-level authorization bypass | function_bypass, privilege_escalation, admin_access |
| **BOLA** | Object-level access bypass and cross-customer data access | object_access, cross_customer, data_manipulation |
| **CredentialExposure** | Hardcoded credentials, token leakage, misconfigured access | hardcoded, token_leak, misconfigured |
| **SensitiveInfoDisclosure** | Training data extraction, architecture disclosure | training_data, architecture, config_leak |

## Recommended Datasets

| Preset | Relevance | Description |
|--------|:---------:|-------------|
| **advbench** | Primary | 520 adversarial harmful goals (injection, jailbreak) |
| **harmbench_contextual** | Primary | 100 contextual prompts requiring instruction override |
| **prompt_injections** | Primary | 662 prompt injection samples (deepset) |
| **jailbreakbench** | Primary | 100 curated jailbreak behaviours (NeurIPS 2024) |
| **strongreject** | Primary/Secondary | 324 forbidden prompts for jailbreak / guardrail testing |
| **saladbench_attack** | Secondary | 5K attack-enhanced safety prompts (jailbreak methods) |
| **wmdp_cyber** | Secondary | Cybersecurity hazardous knowledge (SSRF, SQLi, shell) |
| **harmbench** | Secondary | 200 harmful behaviours (insecure output scenarios) |
| **agentharm** | Secondary | 176+ harmful agentic tasks (plugin/tool interactions) |

:::info Attack Coverage
Most cybersecurity vulnerabilities support the full attack suite (Baseline + PAIR + AdvPrefix). Vulnerabilities without datasets (SupplyChain, DebugAccess, RBAC, BFLA, BOLA, CredentialExposure) require custom goals.
:::

## Quick Start

```python
from hackagent.risks import get_profiles_by_risk, RiskCategory

profiles = get_profiles_by_risk(RiskCategory.CYBERSECURITY)
for p in profiles:
    ds = ", ".join(p.dataset_presets) or "custom goals needed"
    print(f"{p.name}: {ds}")
```
