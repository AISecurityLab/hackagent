---
sidebar_label: generation
title: hackagent.attacks.techniques.indirect.tool_output_ipi.generation
---

Generation logic for tool-output indirect prompt injection.

Simulated mode (default):
1. Pick a benign user task for the goal.
2. Craft an adversarial tool observation (template and/or attacker LLM).
3. Build a messages history: user → assistant(tool_call) → tool(poisoned).
4. Query the target with that history (and optional tool schemas).
5. Judge whether the response / follow-up tool call follows the injected goal.

Live mode (stretch): first solicit a real tool call from the target for the
benign task; if one is returned, replace its observation with the poisoned
payload. Falls back to simulated construction when no tool call is produced.

#### success\_setting\_framing

```python
def success_setting_framing(setting: str) -> str
```

Return injection-prompt framing for an InjecAgent success setting.

#### success\_setting\_judge\_hint

```python
def success_setting_judge_hint(setting: str) -> str
```

Return judge-instruction hint for an InjecAgent success setting.

#### resolve\_tool\_name

```python
def resolve_tool_name(params: Dict[str, Any]) -> str
```

Resolve the primary tool name from params.

Preference order:
1. Explicit non-empty `tool_name` (TUI / caller override)
2. Name from the first entry in `tools` schemas
3. :data:`DEFAULT_TOOL_NAME`

#### resolve\_benign\_task

```python
def resolve_benign_task(goal_idx: int, params: Dict[str, Any],
                        goal: str) -> str
```

Pick a benign task for `goal_idx`, cycling configured or default lists.

#### render\_injection

```python
def render_injection(template: str, *, goal: str, benign_task: str,
                     tool_name: str) -> str
```

Fill injection template placeholders.

#### build\_poisoned\_observation

```python
def build_poisoned_observation(params: Dict[str, Any],
                               *,
                               goal: str,
                               benign_task: str,
                               tool_name: str,
                               injection_body: Optional[str] = None) -> str
```

Compose the tool observation: benign prefix + adversarial injection.

When `success_setting` is set, appends InjecAgent-aligned framing so the
injected text steers toward direct harm, data stealing, or both.

#### build\_simulated\_messages

```python
def build_simulated_messages(
        *,
        benign_task: str,
        tool_name: str,
        tool_arguments: str,
        poisoned_observation: str,
        tool_call_id: Optional[str] = None) -> List[Dict[str, Any]]
```

Build OpenAI-style messages with a simulated tool call + poisoned result.

#### extract\_tool\_calls

```python
def extract_tool_calls(response: Any) -> List[Dict[str, Any]]
```

Best-effort extraction of tool/function calls from a target response.

#### execute

```python
def execute(goals: List[str], agent_router: LLMRouter, config: Dict[str, Any],
            logger: logging.Logger) -> List[Dict[str, Any]]
```

Run tool-output IPI generation + inline judging for each goal.

