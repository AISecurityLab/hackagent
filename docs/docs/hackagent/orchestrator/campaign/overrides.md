---
sidebar_label: overrides
title: hackagent.orchestrator.campaign.overrides
---

Endpoint overrides and local-server readiness for running a campaign file.

A campaign file pins each model&#x27;s endpoint, but the servers a run actually
reaches are often decided at launch (a SLURM job, a notebook, a one-off CLI
run). These helpers rewrite a campaign&#x27;s model connections to point at the
servers given at run time, and wait for local servers to come up and serve the
models the campaign needs. They operate on the plain dict a
:class:`CampaignSpec` dumps to, so a caller can edit connections in place and
re-validate.

The CLI `campaign` command and `scripts/run_campaign.py` both build on
these; neither logic lives in the other.

## EndpointOverrides Objects

```python
@dataclass(frozen=True)
class EndpointOverrides()
```

Run-time endpoints to point campaign models at.

`ollama` repoints every (Ollama) model. The OpenAI-compatible overrides
split by role: `openai` moves the target and the judges sharing its
server, `judge` moves the other judges, `attacker` moves attack role
models. `ollama` cannot be combined with the OpenAI-compatible ones.

## ServerReadiness Objects

```python
@dataclass(frozen=True)
class ServerReadiness()
```

How long to wait for local servers, and the pids to watch.

#### campaign\_models

```python
def campaign_models(
        values: dict[str, Any]) -> Iterator[tuple[str, dict[str, Any]]]
```

Yield `(kind, model)` for every model a campaign names.

`kind` is `target`, `role` or `judge`. Models are the mutable
dicts of `values`, so callers can rewrite their connections in place.

#### installed\_models

```python
def installed_models(endpoint: str,
                     timeout: float,
                     server_pid: int | None = None,
                     *,
                     provider: str = "ollama") -> set[str]
```

Wait for readiness and return installed or served model identifiers.

#### apply\_endpoint\_overrides

```python
def apply_endpoint_overrides(values: dict[str, Any],
                             overrides: EndpointOverrides) -> None
```

Point a campaign&#x27;s models at `overrides`&#x27; servers, in place.

**Raises**:

- `ValueError` - if the overrides do not fit the campaign&#x27;s model
  connections (wrong wire type, no role model to point at, or
  Ollama mixed with OpenAI-compatible overrides).

#### wait\_for\_servers

```python
def wait_for_servers(values: dict[str, Any],
                     readiness: ServerReadiness) -> None
```

Wait for every local server and check it serves the models it must.

**Raises**:

- `ValueError` - if a local model has no endpoint.
- `RuntimeError` - if a server never becomes ready or lacks a model.

