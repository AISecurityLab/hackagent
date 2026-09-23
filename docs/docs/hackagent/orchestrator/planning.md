---
sidebar_label: planning
title: hackagent.orchestrator.planning
---

Attack planner.

An LLM chooses one registered technique, goals and parameters. Parameters
are validated against the technique&#x27;s pydantic JSON schema (the registry),
not the TUI form specs.

## PlannerError Objects

```python
class PlannerError(Exception)
```

Raised when the planner cannot produce a usable plan.

## SchemaField Objects

```python
@dataclass
class SchemaField()
```

One tunable parameter taken from a technique JSON schema.

## AttackPlan Objects

```python
@dataclass
class AttackPlan()
```

An LLM-chosen attack strategy for a target.

#### to\_attack\_config

```python
def to_attack_config() -> Dict[str, Any]
```

Build a runnable ``attack_config`` dict for ``HackAgent.hack``.

#### summary

```python
def summary() -> str
```

Human-readable one-screen summary of the plan.

#### build\_web\_target

```python
def build_web_target(
        url: str,
        *,
        name: Optional[str] = None,
        headless: bool = True,
        input_selector: Optional[str] = None,
        reply_selector: Optional[str] = None,
        launcher_selector: Optional[str] = None,
        dismiss_consent: bool = True,
        llm_fallback_model: Optional[str] = None,
        timeout: Optional[int] = None) -> Tuple[str, Dict[str, Any]]
```

Build the ``(&quot;web&quot;, operational_config)`` target for a live-browser chatbot.

#### schema\_fields

```python
def schema_fields(attack_id: str) -> List[SchemaField]
```

Flatten a technique config&#x27;s JSON schema into planner fields.

#### build\_attack\_catalog

```python
def build_attack_catalog(*,
                         include_advanced: bool = False
                         ) -> List[Dict[str, Any]]
```

Serialize registered techniques and their JSON-schema parameters.

#### plan\_attack

```python
def plan_attack(target: Dict[str, Any],
                *,
                model: str = DEFAULT_PLANNER_MODEL,
                goals: Optional[List[str]] = None,
                api_key: Optional[str] = None,
                temperature: float = 0.2,
                max_tokens: int = 1500) -> AttackPlan
```

Ask an LLM to choose an attack strategy and parameters for ``target``.

## AutoPlanResult Objects

```python
@dataclass
class AutoPlanResult()
```

Combined output of :func:`auto_plan`.

#### auto\_plan

```python
def auto_plan(url: str,
              *,
              model: str = DEFAULT_PLANNER_MODEL,
              goals: Optional[List[str]] = None,
              target_kwargs: Optional[Dict[str, Any]] = None,
              **plan_kwargs: Any) -> AutoPlanResult
```

Build a web target for ``url`` and plan an attack against it.

