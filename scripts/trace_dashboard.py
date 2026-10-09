"""Render a run's search traces as a self-contained HTML dashboard.

Reads ``<run_id>.traces.jsonl`` (and, next to it, the result rows
``<run_id>.jsonl`` or ``.json`` for goals and verdicts) and writes one HTML
file with no external assets, so it opens offline from any machine::

    python -m scripts.trace_dashboard logs/runs/slurm-53809
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

TEMPLATE = Path(__file__).with_name("trace_dashboard.html")
PLACEHOLDER = "__TRACE_DATA__"
SUFFIX = ".traces.jsonl"


def read_rows(directory: Path, run_id: str) -> list[dict[str, Any]]:
    """Result rows of a run, from whichever output format was written."""
    jsonl = directory / f"{run_id}.jsonl"
    if jsonl.exists():
        lines = jsonl.read_text(encoding="utf-8").splitlines()
        return [json.loads(line) for line in lines if line.strip()]
    plain = directory / f"{run_id}.json"
    return json.loads(plain.read_text(encoding="utf-8")) if plain.exists() else []


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
    run_id = traces.name.removesuffix(SUFFIX)
    goals: dict[tuple[str, int], dict[str, Any]] = defaultdict(
        lambda: {"goal": None, "nodes": {}, "attempts": {}}
    )
    campaign = ""
    for row in read_rows(traces.parent, run_id):
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
        "path", type=Path, help="a *.traces.jsonl file or a run directory"
    )
    parser.add_argument("-o", "--output", type=Path, help="output HTML file")
    args = parser.parse_args()

    files = sorted(args.path.glob(f"*{SUFFIX}")) if args.path.is_dir() else [args.path]
    if not files:
        parser.error(f"no *{SUFFIX} files in {args.path}")
    output = args.output or (
        args.path / "trace-dashboard.html"
        if args.path.is_dir()
        else args.path.with_name(
            args.path.name.removesuffix(SUFFIX) + ".dashboard.html"
        )
    )
    output.write_text(render([load_run(file) for file in files]), encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
