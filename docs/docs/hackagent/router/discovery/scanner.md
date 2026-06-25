---
sidebar_label: scanner
title: hackagent.router.discovery.scanner
---

Agentic attack planner.

Given a chatbot target (a website URL, driven by the ``web`` provider) and the
catalog of HackAgent attack techniques, an LLM chooses the attack strategy,
goals, and tuning parameters — instead of the operator hand-picking
``--attack-type tap`` and fiddling with knobs.

The model is constrained to the real attack catalog
(``hackagent.cli.tui.attack_specs``, imported lazily so this module never drags
in the TUI): it may only pick a registered technique, and every parameter it
proposes is validated/coerced against that technique&#x27;s spec, so the resulting
:class:`AttackPlan` is always runnable.

:func:`auto_plan` is the end-to-end entry point: it builds a ``web`` target from
a URL and asks the planner to pick a strategy. Planning is pure LLM reasoning —
it does not touch the target. The browser only runs when the attack executes.

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

The live page is the target — there is no endpoint discovery. ``endpoint``
mirrors ``url`` so the router&#x27;s generic plumbing has something to store.

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

**Attributes**:

- `attack_type` - A registered technique key (``&quot;tap&quot;``, ``&quot;pair&quot;``…).
- `goals` - Red-team objectives to pursue against the target.
- `parameters` - Validated, nested strategy parameters (e.g.
- ```{"tap_params"` - {&quot;depth&quot;: 3}}``) ready to merge into an
  ``attack_config``.
- ``2 - The model&#x27;s explanation for the choice.
- ``3 - The model&#x27;s self-reported confidence (0.0–1.0).
- ``4 - Notes about anything coerced/dropped during validation.
- ``5 - The raw JSON object the model returned.
- ``6 - The planner model used.

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

#### build\_attack\_catalog

```python
def build_attack_catalog(*,
                         include_advanced: bool = False
                         ) -> List[Dict[str, Any]]
```

Serialize the registered attack specs into a compact catalog.

The catalog is what the planner is shown and constrained to: it lists every
technique and its tunable parameters. Advanced/auth fields (attacker model,
API keys…) are excluded by default — the planner picks the *strategy*, while
model credentials come from the run config.

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

Ask an LLM to choose an attack strategy + parameters for ``target``.

**Arguments**:

- `target` - A target operational config (e.g. from :func:`build_web_target`);
  should include ``url``/``name``.
- `model` - LiteLLM model string for the planner.
- `goals` - Optional fixed goals; when omitted the model proposes them.
- ``0 - Optional explicit API key (else LiteLLM env resolution).
- ``1 - Planner sampling temperature.
- ``2 - Planner response cap.
  

**Returns**:

  A validated :class:``3.
  

**Raises**:

- ``4 - if litellm is unavailable, the call fails, or the model&#x27;s
  output can&#x27;t be turned into a valid plan.

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
              **plan_kwargs) -> AutoPlanResult
```

Build a ``web`` target for ``url`` and plan an attack against it.

The end-to-end agentic entry point: target → LLM strategy choice. Planning
is pure reasoning and does not touch the target; the browser only runs when
the chosen plan is executed.

