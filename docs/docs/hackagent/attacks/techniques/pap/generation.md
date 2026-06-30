---
sidebar_label: generation
title: hackagent.attacks.techniques.pap.generation
---

PAP generation module.

Core algorithm: for each goal, iterate over selected persuasion techniques
from the taxonomy.  For each technique:
1. Build a mutation prompt using the technique&#x27;s definition and examples.
2. Send to the attacker LLM to paraphrase the goal into a persuasive variant.
3. Send the persuasive prompt to the target model.
4. Evaluate the response with a judge.
5. If the judge confirms a jailbreak → early stop.

Uses the same inline ``_StepJudge`` pattern as BoN for judge evaluation
inside the generation loop.

Based on: https://arxiv.org/abs/2401.06373

#### execute

```python
def execute(goals: List[str], agent_router: AgentRouter,
            config: Dict[str, Any], logger: logging.Logger) -> List[Dict]
```

Generate persuasive prompts, query the target, and judge inline.

For each goal:
1. Iterate over selected persuasion techniques.
2. Use the attacker LLM to paraphrase the goal.
3. Send the persuasive prompt to the target.
4. Judge the response.  If jailbreak → early stop.

**Arguments**:

- `goals` - List of harmful prompt strings.
- `agent_router` - Router for the target model.
- `config` - Configuration dictionary.
- `logger` - Logger instance.
  

**Returns**:

  List of result dicts, one per goal.

