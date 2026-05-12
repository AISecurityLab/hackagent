---
sidebar_position: 6
---

# Dataset Troubleshooting

Use this page when dataset loading fails, returns zero goals, or behaves unexpectedly.

## 1. No Goals Loaded

### Symptoms
- Error about missing `goals` / empty dataset
- Attack starts but immediately stops with no samples

### Checks
1. Confirm you provided either `dataset` or explicit `goals` in `attack_config`.
2. If using presets, verify the preset name in [Presets](./presets).
3. Remove `offset` temporarily; it may skip all rows when combined with a small `limit`.
4. Disable filters temporarily (`filter_field`, `filter_value`) to confirm the source contains matching rows.

## 2. HuggingFace Dataset Fails to Load

### Symptoms
- Dataset not found
- Split/config errors
- Authentication errors for private repos

### Checks
1. Verify `dataset.path` is correct (`owner/dataset_name`).
2. Confirm `split` exists for that dataset.
3. If needed, set the correct config name in `dataset.name`.
4. For private datasets, authenticate with `huggingface-cli login` first.
5. Ensure `goal_field` exists in records.

Reference: [HuggingFace Provider](./huggingface)

## 3. Local File Provider Issues

### Symptoms
- File not found
- Field extraction errors
- Empty goals from JSON/CSV

### Checks
1. Use an absolute path or confirm relative path from your current working directory.
2. Verify file format is supported (`.json`, `.jsonl`, `.csv`, `.txt`).
3. For JSON/CSV, ensure `goal_field` matches a real column/key.
4. For TXT, use one goal per line and remove empty lines.

Reference: [File Provider](./file)

## 4. Reproducibility Problems

### Symptoms
- Different results across runs with the same dataset source

### Checks
1. Set both `shuffle: true` and a fixed `seed`.
2. Keep the same `limit` and `offset` across runs.
3. Pin dataset version when possible (especially for frequently updated external datasets).

## 5. Slow Dataset Loading

### Quick Fixes
1. Reduce `limit` for local debugging.
2. Use presets for fast startup before moving to large external datasets.
3. Avoid heavy filtering in the first pass; validate with a small sample first.

## 6. Debug Checklist

Run this minimal pattern to isolate dataset issues:

```python
attack_config = {
    "attack_type": "baseline",
    "dataset": {
        "preset": "simplesafetytests",
        "limit": 10,
        "shuffle": False,
    },
}
```

If this works, increase complexity gradually: add `shuffle`, then `seed`, then custom provider/path/filter options.

## See Also

- [Dataset Providers](/datasets)
- [Presets](./presets)
- [HuggingFace Provider](./huggingface)
- [File Provider](./file)
- [Custom Providers](./custom-providers)
