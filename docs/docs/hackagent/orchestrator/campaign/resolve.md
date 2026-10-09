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

#### resolve\_campaign

```python
def resolve_campaign(
        spec: CampaignSpec,
        *,
        build: ModelBuilder = build_model,
        load: GoalLoader = load_goals,
        build_embed: EmbedderBuilder = build_embedder) -> ResolvedCampaign
```

Instantiate everything `spec` describes.

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

