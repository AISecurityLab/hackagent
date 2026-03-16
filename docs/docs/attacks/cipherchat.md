---
sidebar_position: 9
---

# CipherChat

CipherChat is a cipher-based jailbreak attack that converts the user goal into a non-natural language (cipher) before querying the target model.

This implementation integrates the full attack workflow from the original project and paper:

- Paper: *GPT-4 Is Too Smart To Be Safe: Stealthy Chat with LLMs via Cipher* (ICLR 2024)
- Upstream code: https://github.com/RobustNLP/CipherChat (MIT)

## Overview

CipherChat applies three core steps:

1. Build a system prompt that frames the model as a cipher expert.
2. Encode the harmful goal with the selected cipher.
3. Decode the model response back to natural language and evaluate it with HackAgent judges.

## Supported Ciphers

The integrated implementation supports all ciphers from the original code:

- `baseline`
- `unchange`
- `caesar`
- `unicode`
- `morse`
- `atbash`
- `utf`
- `ascii`
- `gbk`
- `selfdefine`

## Basic Usage

```python
from hackagent import HackAgent, AgentTypeEnum

agent = HackAgent(
    name="target_agent",
    endpoint="https://openrouter.ai/api/v1",
    agent_type=AgentTypeEnum.OPENAI_SDK,
    api_key="${HACKAGENT_API_KEY}",
    adapter_operational_config={
        "name": "google/gemma-3n-e4b-it",
        "api_key": "${OPENROUTER_API_KEY}",
        "endpoint": "https://openrouter.ai/api/v1",
    },
)

attack_config = {
    "attack_type": "cipherchat",
    "goals": [
        "Explain how to pick a lock"
    ],
    "cipherchat_params": {
        "encode_method": "caesar",
        "use_system_role": True,
        "use_demonstrations": True,
        "demonstration_toxicity": "toxic",
        "instruction_type": "Crimes_And_Illegal_Activities",
        "language": "en",
        "num_demonstrations": 3,
        "decode_response": True,
    },
    "judges": [
        {
            "identifier": "openai/gpt-4o-mini",
            "type": "harmbench",
            "agent_type": "OPENAI_SDK",
            "api_key": "${OPENROUTER_API_KEY}",
            "endpoint": "https://openrouter.ai/api/v1",
        }
    ]
}

results = agent.hack(attack_config=attack_config)
```

## Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `cipherchat_params.encode_method` | Cipher used to encode goals | `caesar` |
| `cipherchat_params.use_system_role` | Include cipher-expert role prompt | `True` |
| `cipherchat_params.use_demonstrations` | Include encoded demonstrations | `True` |
| `cipherchat_params.demonstration_toxicity` | Demonstration set (`toxic`/`harmless`) | `toxic` |
| `cipherchat_params.instruction_type` | Demonstration category | `Crimes_And_Illegal_Activities` |
| `cipherchat_params.language` | Demonstration language (`en`/`zh`) | `en` |
| `cipherchat_params.num_demonstrations` | Number of demonstrations to include | `3` |
| `cipherchat_params.decode_response` | Decode model output before evaluation | `True` |
| `batch_size` | Concurrent target requests | `8` |
| `batch_size_judge` | Concurrent judge requests | `1` |

## Notes

- `encode_method="baseline"` disables demonstrations, matching the original implementation behavior.
- Judge evaluation is performed on decoded responses, aligned with the CipherChat paper workflow.
- The integrated prompt and demonstration resources include the same categories used in the upstream release.
