---
sidebar_label: labelling
title: hackagent.datasets.labelling
---

Label goals with the risk taxonomy using a classifier model.

Goals that already carry labels (intents set them) are left alone; the rest
go to the model in numbered batches, one line of reply per goal. Labelling
fails open: a goal the model could not place gets the unclassified labels,
and after the first failed call the model is not asked again, so an outage
costs one timeout rather than one per batch.

#### BATCH\_SIZE

Goals per request: keeps the numbering parseable and within the token budget.

#### TOKENS\_PER\_GOAL

Output budget per goal; one line holds both labels.

#### request

```python
def request(goals: Sequence[str]) -> list[dict[str, str]]
```

The messages asking for one label per goal, numbered from 1.

#### read\_reply

```python
def read_reply(text: str, count: int) -> dict[int, str]
```

Each goal number&#x27;s subcategory answer; the first line for a number wins.

From `3. CATEGORY: E | SUBCATEGORY: E2` the answer is `E2`. A line
without fields is the answer itself (`3. E2`).

#### label\_goals

```python
async def label_goals(goals: Sequence[Goal],
                      model: ClassifierModel,
                      *,
                      batch_size: int = BATCH_SIZE,
                      concurrency: int = 1) -> list[Goal]
```

`goals` with taxonomy labels on every one.

