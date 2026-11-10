# tools/

Developer checks and offline analysis. None of it ships in the `hackagent`
package; build and release tooling is in [`deploy/`](../deploy/README.md).

## lint/: import contracts

`import_contracts.py` defines the custom import-linter contract
`LoggingHandlersContract`, registered in `pyproject.toml`
(`[tool.importlinter]`). It runs with the other contracts in CI and pre-commit:

```bash
uv run lint-imports
```

## traces/: offline trace dashboard

`trace_dashboard.py` renders a campaign run's search traces into one
self-contained HTML file (the `trace_dashboard.html` template, kept next to
it), which opens offline anywhere.

```bash
uv run python -m tools.traces.trace_dashboard logs/runs/<run_id>
uv run python -m tools.traces.trace_dashboard logs/runs        # every run in the folder
uv run python -m tools.traces.trace_dashboard logs/runs/<run_id> -o dashboard.html
```

- **Reads** a run folder's `traces.jsonl` and its `results.jsonl` or `results.json`
  (a campaign run with `execution.output.save_traces` enabled), or older flat
  `<run_id>.traces.jsonl` files.
- **Writes** `trace-dashboard.html` in the folder given, unless `-o` names a file.
- An attack's run-level trace (work shared by every goal) is listed first under
  that attack, labelled `run`.

Tested by `tests/unit/tools/test_trace_dashboard.py`.
