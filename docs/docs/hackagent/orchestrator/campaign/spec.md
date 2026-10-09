---
sidebar_label: spec
title: hackagent.orchestrator.campaign.spec
---

Schema of a campaign file.

A campaign reads top to bottom as the run does: load the `dataset`, send
every goal through each of the `attacks` to the `target`, score the
replies with the `evaluation` judges, and run it all under the
`execution` policy. Validation here is purely structural; whether an
attack&#x27;s parameters and roles fit the attack is checked when the campaign
is resolved.

## CampaignMetadata Objects

```python
class CampaignMetadata(_Spec)
```

A name for the run, used in logs, stored results and output file names.

## ScoringSpec Objects

```python
class ScoringSpec(_Spec)
```

How a judge&#x27;s reply is read: which prompt the judge gets and how its answer
is parsed into a score.

## AttackSpec Objects

```python
class AttackSpec(_Spec)
```

One attack technique to run against the target: which one, how to tune it,
and which helper models it drives.

## JudgeSpec Objects

```python
class JudgeSpec(ModelConfig)
```

A judge: a model that reads the target&#x27;s reply and decides whether the
attack succeeded, plus how its answer is scored.

## AuditSpec Objects

```python
class AuditSpec(_Spec)
```

Measure the judge panel against labelled samples before trusting it.

Off by default: an audit is a pass of the whole panel over its calibration
dataset before a single goal is attacked, and robustness repeats that pass per
wrapper. Switch it on when the cost of a wrong success rate is higher than the
cost of those calls.

## GuardrailModelConfig Objects

```python
class GuardrailModelConfig(ModelConfig)
```

A guardrail: a classifier model that decides whether a text is safe.

## CategoryClassifierConfig Objects

```python
class CategoryClassifierConfig(ModelConfig)
```

A model that labels each goal with the risk taxonomy before the run.

## CampaignDatasetSpec Objects

```python
class CampaignDatasetSpec(DatasetSpec)
```

Where the goals come from and which of them to run.

Goals are loaded from the `source`, optionally labelled by the
`classifier`, then narrowed down by the `selection`.

## GuardrailsSpec Objects

```python
class GuardrailsSpec(_Spec)
```

Classifier models that defend the target.

`before` checks each prompt and blocks an unsafe one before it reaches the
target; `after` checks the reply and withholds an unsafe one. Both fail open:
an unavailable or unparseable classifier lets the text through, so a
misconfigured guardrail never blocks the whole run. Use this to measure an
attack against a *defended* target.

## EvaluationSpec Objects

```python
class EvaluationSpec(_Spec)
```

The judge panel that scores every reply from the target.

Each judge votes on whether the reply is a jailbreak; the panel combines the
votes into one verdict. A judge that fails or answers unreadably abstains
instead of voting.

## ConcurrencySpec Objects

```python
class ConcurrencySpec(_Spec)
```

How much work may be in flight at once, shared by every attack.

## RetrySpec Objects

```python
class RetrySpec(_Spec)
```

Extra attempts after a provider error (timeouts, rate limits, 5xx).

## OutputSpec Objects

```python
class OutputSpec(_Spec)
```

Files written for each run, next to the results stored in the database.

## StorageSpec Objects

```python
class StorageSpec(_Spec)
```

Where results are recorded so they can be browsed later.

## ExecutionSpec Objects

```python
class ExecutionSpec(_Spec)
```

How the run behaves: ordering, limits, error handling, output and storage.
Every field has a safe default.

## CampaignSpec Objects

```python
class CampaignSpec(_Spec)
```

A complete campaign: what to attack, with what, and how to judge it.

It reads top to bottom as the run does: load the `dataset`, send every goal
through each of the `attacks` to the `target` (optionally behind
`guardrails`), score the replies with the `evaluation` judges, and run it
all under the `execution` policy.

