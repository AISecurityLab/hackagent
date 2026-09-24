---
sidebar_label: planner
title: hackagent.orchestrator.planning.planner
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

Build a runnable `attack_config` dict for :meth:`hackagent.client.Target.hack`.

#### summary

```python
def summary() -> str
```

Human-readable one-screen summary of the plan.

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

Ask an LLM to choose an attack strategy and parameters for `target`.

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

Build a web target for `url` and plan an attack against it.

