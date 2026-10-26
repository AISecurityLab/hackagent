---
sidebar_label: resolve
title: hackagent.orchestrator.campaign.resolve
---

Turn a campaign spec into the objects a run needs.

Resolution loads the goals, creates every model client (target, attack
roles, judges), and constructs each attack from its parameters plus a
traced completion for each of its role models. No request is sent to any
model. The evaluation panel is built here too, and the runner hands it to
iterative attacks as they search.

#### EmbedderBuilder

Builds the texts-in, vectors-out callable an embedder role receives.

## ResolvedAttack Objects

```python
@dataclass(frozen=True)
class ResolvedAttack()
```

A ready-to-run attack and the configuration it was built from.

#### configuration

Parameters and role model names, as recorded with the run.

## ResolvedCampaign Objects

```python
@dataclass(frozen=True)
class ResolvedCampaign()
```

#### probes

One reachability check per distinct model, for preflight.

#### resolve\_campaign

```python
def resolve_campaign(
        spec: CampaignSpec,
        *,
        build: ModelBuilder = build_model,
        load: GoalLoader = load_goals,
        build_embed: EmbedderBuilder = build_embedder,
        settings: Optional[Settings] = None) -> ResolvedCampaign
```

Instantiate everything `spec` describes.

Gateway credentials come from `settings`, resolved once if omitted.
An explicit model connection `api_key` takes precedence.

#### resolve\_attack

```python
def resolve_attack(
        spec: AttackSpec,
        build: ModelBuilder,
        *,
        retries: int = 0,
        build_embed: EmbedderBuilder = build_embedder) -> ResolvedAttack
```

Construct an attack, binding each role model to the shape it declares.

A completion role receives a traced chat callable; an embedder role
receives a texts-in, vectors-out callable from the embeddings endpoint.

#### build\_panel

```python
def build_panel(spec: EvaluationSpec,
                build: ModelBuilder,
                *,
                retries: int = 0) -> Optional[Panel]
```

Bind every judge to its model. `None` when no judge is configured.

#### resolution\_summary

```python
def resolution_summary(resolved: ResolvedCampaign) -> dict[str, str]
```

What resolving the campaign found, as label-value rows.

The facts a run is about to act on: how many goals were loaded, which
attacks were built, and which optional parts are switched on. The CLI
prints them as a table and the builder logs them before it starts, so
they are written once here and cannot drift apart.

