---
sidebar_label: generation
title: hackagent.attacks.techniques.fc.generation
---

FC-Attack generation and execution module.

Provides two entry points:

- ``execute_fc`` — Renders flowchart images and sends them to a VLM.
- ``execute_tfc`` — Serializes flowcharts as text and sends to any LLM.

Shared logic (step decomposition, target execution, result recording) is
factored into private helpers.

Based on: Zhang et al., &quot;FC-Attack: Jailbreaking Multimodal Large
Language Models via Auto-Generated Flowcharts&quot; (EMNLP 2025 Findings)

#### execute\_fc

```python
def execute_fc(goals: List[str], agent_router: AgentRouter, config: Dict[str,
                                                                         Any],
               logger: logging.Logger) -> List[Dict[str, Any]]
```

FC-Attack: render flowchart images and send to a Vision-Language Model.

Pipeline:
1. Decompose each goal into numbered steps.
2. Optionally truncate the last step to induce completion.
3. Render steps as a flowchart image (vertical/horizontal/tortuous).
4. Send the image + jailbreak text prompt to the target VLM.

**Arguments**:

- `goals` - List of harmful prompts to encode as flowcharts.
- `agent_router` - Router for target model communication.
- `config` - Configuration dictionary with ``fc_params``.
- `logger` - Logger instance.
  

**Returns**:

  List of result dicts compatible with the evaluation step.

#### execute\_tfc

```python
def execute_tfc(goals: List[str], agent_router: AgentRouter, config: Dict[str,
                                                                          Any],
                logger: logging.Logger) -> List[Dict[str, Any]]
```

tFC-Attack: serialize flowcharts as text and send to any LLM.

Pipeline:
1. Decompose each goal into numbered steps.
2. Optionally truncate the last step to induce completion.
3. Serialize steps in the configured text format (ascii, mermaid, etc.).
4. Send the text flowchart + jailbreak prompt to the target LLM.

**Arguments**:

- `goals` - List of harmful prompts to encode as flowcharts.
- `agent_router` - Router for target model communication.
- `config` - Configuration dictionary with ``tfc_params``.
- `logger` - Logger instance.
  

**Returns**:

  List of result dicts compatible with the evaluation step.

