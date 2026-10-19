# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Every campaign the documentation teaches must be one the code accepts.

The pages are prose, so nothing compiles them. A field renamed in the spec
leaves them describing something that no longer validates, and the reader
finds out by running it. Each `{"version": 1, ...}` literal in a Python
block is parsed, its variables filled with something the slot accepts, and
handed to `CampaignSpec`.

What this cannot check is whether the *values* are sensible — only that the
shape is one the loader takes.
"""

import ast
import re
from pathlib import Path

import pytest

from hackagent.orchestrator.campaign.spec import CampaignSpec

TARGET = {
    "name": "t",
    "connection": {
        "provider": "local",
        "type": "OPENAI_SDK",
        "endpoint": "http://localhost:8080/v1",
    },
}
MODEL = {"name": "llama3", "connection": {"provider": "ollama", "type": "OLLAMA"}}
NAMED = {
    "TARGET": TARGET,
    "target": TARGET,
    "production": TARGET,
    "JUDGE": {**MODEL, "scoring": {"type": "harmbench"}},
    "JUDGE_MODEL": MODEL,
    "ATTACKER": MODEL,
    "OLLAMA": MODEL["connection"],
}
HOLE = "__HOLE__"


class Stub(ast.NodeTransformer):
    def visit_Name(self, node):
        return ast.Constant(value=f"__NAMED__{node.id}" if node.id in NAMED else HOLE)

    def visit_Attribute(self, node):
        return ast.Constant(value=HOLE)

    def visit_Subscript(self, node):
        return ast.Constant(value=HOLE)

    def visit_Call(self, node):
        return ast.Constant(value=HOLE)

    def visit_JoinedStr(self, node):
        return ast.Constant(value="a name")

    def visit_Dict(self, node):
        """`{**NAME, ...}` is spread here, since literal_eval cannot."""
        keys, values = [], []
        for key, value in zip(node.keys, node.values):
            if key is None:
                spread = NAMED.get(getattr(value, "id", ""), {})
                for k, v in spread.items():
                    keys.append(ast.Constant(value=k))
                    values.append(ast.Constant(value=v))
                continue
            keys.append(self.visit(key))
            values.append(self.visit(value))
        return ast.Dict(keys=keys, values=values)


def fill(value, slot=""):
    """Replace holes with something the slot actually accepts."""
    if isinstance(value, str):
        if value.startswith("__NAMED__"):
            return NAMED[value[len("__NAMED__") :]]
        if value == HOLE:
            return {
                "goals": ["a goal"],
                "name": "harmbench",
                "attack": "baseline",
                # A page may compute an attack's roles rather than spell them
                # out, since which roles an attack takes is the attack's own
                # business.
                "roles": {"attacker": MODEL},
                # A page may name a judge of its own before using it.
                "judges": {**MODEL, "scoring": {"type": "harmbench"}},
            }.get(slot, "harmbench")
        return value
    if isinstance(value, dict):
        return {k: fill(v, k) for k, v in value.items()}
    if isinstance(value, list):
        return [fill(v, slot) for v in value]
    return value


def campaigns(block):
    for m in re.finditer(r'\{\s*\n\s*"version": 1,', block):
        start, depth = m.start(), 0
        for i, ch in enumerate(block[start:], start):
            depth += (ch == "{") - (ch == "}")
            if depth == 0:
                yield block[start : i + 1]
                break


DOCS = Path(__file__).resolve().parents[3] / "docs" / "docs"


def documented_campaigns():
    """Every campaign literal in the docs, with the page it came from."""
    for path in sorted(DOCS.rglob("*.md")):
        for block in re.findall(
            r"```python\n(.*?)```", path.read_text(encoding="utf-8"), re.S
        ):
            for snippet in campaigns(block):
                yield path.relative_to(DOCS).as_posix(), snippet


FOUND = list(documented_campaigns())


def test_the_docs_teach_campaigns_at_all():
    """A parser that matched nothing would make the test below vacuous."""
    assert len(FOUND) > 20, f"only found {len(FOUND)} campaigns in the docs"


@pytest.mark.parametrize(
    ("page", "snippet"), FOUND, ids=[f"{p}#{n}" for n, (p, _) in enumerate(FOUND)]
)
def test_the_documented_campaign_is_one_the_code_accepts(page, snippet):
    tree = Stub().visit(ast.parse(snippet, mode="eval"))
    values = fill(ast.literal_eval(ast.fix_missing_locations(tree)))
    # `attack.technique` stubs to a string that is not a registered attack.
    if isinstance(values.get("attacks"), list):
        values["attacks"] = [
            {**a, "name": "baseline"} if a.get("name") == "harmbench" else a
            for a in values["attacks"]
        ]
    CampaignSpec.model_validate(values)
