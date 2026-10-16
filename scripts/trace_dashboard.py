"""Render a run's search traces as a self-contained HTML dashboard.

Reads a run folder's ``traces.jsonl`` (and, next to it, the result rows
``results.jsonl`` or ``results.json`` for goals and verdicts) and writes one
HTML file with no external assets, so it opens offline from any machine::

    python -m scripts.trace_dashboard logs/runs/<run_id>
    python -m scripts.trace_dashboard logs/runs   # every run in the folder

Older runs written as flat ``<run_id>.traces.jsonl`` files are read too.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

TEMPLATE = Path(__file__).with_name("trace_dashboard.html")
PLACEHOLDER = "__TRACE_DATA__"
TRACES = "traces.jsonl"
LEGACY_SUFFIX = ".traces.jsonl"


def run_id_of(traces: Path) -> str:
    if traces.name == TRACES:
        return traces.parent.name
    return traces.name.removesuffix(LEGACY_SUFFIX)


def read_rows(traces: Path) -> list[dict[str, Any]]:
    """Result rows of a run, from whichever output format was written."""
    directory = traces.parent
    if traces.name == TRACES:
        jsonl, plain = directory / "results.jsonl", directory / "results.json"
    else:
        run_id = run_id_of(traces)
        jsonl, plain = directory / f"{run_id}.jsonl", directory / f"{run_id}.json"
    if jsonl.exists():
        lines = jsonl.read_text(encoding="utf-8").splitlines()
        return [json.loads(line) for line in lines if line.strip()]
    return json.loads(plain.read_text(encoding="utf-8")) if plain.exists() else []


def find_traces(path: Path) -> list[Path]:
    """Trace files of a trace file, a run folder, or a folder of runs."""
    if not path.is_dir():
        return [path]
    if (path / TRACES).exists():
        return [path / TRACES]
    return sorted(path.glob(f"*/{TRACES}")) + sorted(path.glob(f"*{LEGACY_SUFFIX}"))


def attempt_summary(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "request_index": row["request_index"],
        "success": bool(row.get("success")),
        "best_score": row.get("best_score"),
        "explanation": row.get("explanation"),
        "error": row.get("error"),
        "metadata": row.get("attack_metadata") or {},
        "judges": {
            key.removeprefix("explanation_"): value
            for key, value in row.items()
            if key.startswith("explanation_")
        },
    }


def verdict_node(nodes: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The node an attempt's verdict hangs on: its target call, else its first call."""
    calls = [node for node in nodes if node["node"] == "call"]
    targets = [
        node for node in calls if (node.get("data") or {}).get("role") == "target"
    ]
    return (targets or calls or [None])[0]


def load_run(traces: Path) -> dict[str, Any]:
    run_id = run_id_of(traces)
    goals: dict[tuple[str, int], dict[str, Any]] = defaultdict(
        lambda: {"goal": None, "nodes": {}, "attempts": {}}
    )
    campaign = ""
    for row in read_rows(traces):
        entry = goals[(row["attack"], row["goal_index"])]
        entry["goal"] = row.get("goal")
        entry["attempts"][row["request_index"]] = attempt_summary(row)
        campaign = row.get("campaign", campaign)
    for line in traces.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        campaign = record.get("campaign", campaign)
        entry = goals[(record["attack"], record["goal_index"])]
        merged = entry["nodes"]
        # A goal's tree arrives split across its attempts, each carrying only
        # the nodes it produced, so the whole is rebuilt by path.
        for node in record["nodes"]:
            merged.setdefault((node.get("scope", "goal"), tuple(node["path"])), node)
        owner = verdict_node(record["nodes"])
        if owner is not None:
            merged[(owner.get("scope", "goal"), tuple(owner["path"]))]["attempt"] = (
                record["request_index"]
            )

    attacks: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for (attack, goal_index), entry in sorted(goals.items()):
        ordered = sorted(entry["nodes"].items(), key=lambda item: item[0])
        attacks[attack].append(
            {
                "goal_index": goal_index,
                "goal": entry["goal"],
                "nodes": [node for _, node in ordered],
                "attempts": [entry["attempts"][i] for i in sorted(entry["attempts"])],
            }
        )
    return {
        "run_id": run_id,
        "campaign": campaign,
        "attacks": [{"name": name, "goals": found} for name, found in attacks.items()],
    }


def render(runs: list[dict[str, Any]]) -> str:
    payload = json.dumps({"runs": runs}, ensure_ascii=False).replace("<", "\\u003c")
    return TEMPLATE.read_text(encoding="utf-8").replace(PLACEHOLDER, payload, 1)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "path", type=Path, help="a traces file, a run folder, or a folder of runs"
    )
    parser.add_argument("-o", "--output", type=Path, help="output HTML file")
    args = parser.parse_args()

    files = find_traces(args.path)
    if not files:
        parser.error(f"no {TRACES} files in {args.path}")
    if args.output:
        output = args.output
    elif args.path.is_dir():
        output = args.path / "trace-dashboard.html"
    elif args.path.name == TRACES:
        output = args.path.with_name("trace-dashboard.html")
    else:
        output = args.path.with_name(
            args.path.name.removesuffix(LEGACY_SUFFIX) + ".dashboard.html"
        )
    output.write_text(render([load_run(file) for file in files]), encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
