---
sidebar_label: labelling
title: hackagent.datasets.labelling
---

Label goals with the risk taxonomy using a classifier model.

Goals that already carry labels (intents set them) are left alone; the rest
go to the model in numbered batches, one line of reply per goal. Labelling
fails open: a goal the model placed only in a category gets that category
with an unspecified subcategory, one it could not place at all gets the
unclassified labels, and after the first failed call the model is not asked
again, so an outage costs one timeout rather than one per batch.

The prompt keeps the taxonomy grouped by category and asks for only
`<n>. <code>` (for example `3. E2`). Both labels are derived from that
subcategory code. Batches still contain 20 goals by default. Names,
explanations, conflicting codes and older category/subcategory field formats
are rejected rather than guessed. For a single-goal request, one unnumbered
code is also accepted.

#### BATCH\_SIZE

Goals per request: keeps the numbering parseable and within the token budget.

#### TOKENS\_PER\_GOAL

Output budget per goal, including headroom beyond the requested code.

#### request

```python
def request(goals: Sequence[str]) -> list[dict[str, str]]
```

The messages asking for one label per goal, numbered from 1.

#### read\_reply

```python
def read_reply(text: str, count: int) -> dict[int, dict[str, str]]
```

Each goal number&#x27;s labels; the first line for a number wins.

`3. E2` supplies both labels from subcategory E2. A category code
alone supplies an unspecified subcategory. Invalid codes and extra
text are left out. A single-goal reply may be one unnumbered code.

#### place

```python
def place(answer: str) -> Optional[dict[str, str]]
```

Resolve one code, tolerating surrounding Markdown and a trailing period.
Known subcategory codes supply both labels; a category letter supplies an
unspecified subcategory. Unknown codes (including `C99` and `C0`) are rejected.

#### label\_goals

```python
async def label_goals(goals: Sequence[Goal],
                      model: ClassifierModel,
                      *,
                      batch_size: int = BATCH_SIZE,
                      concurrency: int = 1) -> list[Goal]
```

`goals` with taxonomy labels on every one.
