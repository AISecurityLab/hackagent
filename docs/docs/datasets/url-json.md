---
sidebar_position: 4
---

# URL JSON Provider

Load attack goals from remote JSON endpoints directly into memory.

:::tip When to Use
Use the URL JSON provider when you:
- Want to consume a dataset published as a JSON URL
- Need a lightweight source without local files or HuggingFace setup
- Evaluate dynamic/public benchmark feeds
:::

## Configuration Options

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `provider` | string | Yes | — | Must be `"url_json"` |
| `url` | string | Yes | — | HTTPS URL returning JSON |
| `goal_field` | string | No | `"instruction"` | Primary field containing the goal text |
| `fallback_fields` | list | No | `["prompt", "input", "text"]` | Alternative fields if `goal_field` is missing |
| `extra_fields` | list | No | `[]` | Additional fields to keep with each goal |
| `limit` | int | No | — | Maximum number of goals |
| `shuffle` | bool | No | `false` | Randomize goal selection |
| `seed` | int | No | — | Random seed for reproducibility |

---

## Basic Usage

```python
attack_config = {
    "attack_type": "baseline",
    "dataset": {
        "provider": "url_json",
        "url": "https://yunhao-feng.github.io/AgentHazard/data/dataset.json",
        "goal_field": "query",
        "fallback_fields": ["prompt", "input", "text"],
        "limit": 100,
        "shuffle": True,
        "seed": 42,
    },
}

results = agent.hack(attack_config=attack_config)
```

---

## Wrapped JSON Support

The provider accepts both:
- Top-level JSON arrays
- JSON objects containing list keys like `data`, `samples`, `records`, or `items`

Example payloads:

```json
[
  {"query": "Goal A"},
  {"query": "Goal B"}
]
```

```json
{
  "records": [
    {"query": "Goal A"},
    {"query": "Goal B"}
  ]
}
```

---

## Structured Output With Metadata

When you need metadata alongside the goal text, use `extra_fields` and provider-level access:

```python
from hackagent.datasets import get_provider

provider = get_provider(
    "url_json",
    {
        "url": "https://yunhao-feng.github.io/AgentHazard/data/dataset.json",
        "goal_field": "query",
        "extra_fields": ["category", "decomposed_query", "jailbreak_method"],
    },
)

rows = provider.load_goals(limit=5, return_dicts=True)
extras = provider.get_extra_data()

print(rows[0])
print(extras[0])
```

---

## Notes

- The dataset is downloaded once and cached in memory per provider instance.
- Use trusted URLs and pin sources when reproducibility is critical.
- For static/private data, the [File Provider](./file.md) can be preferable.
