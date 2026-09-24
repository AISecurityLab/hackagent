# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Per-strategy ``hackagent eval <strategy>`` commands.

Every strategy command shares the same options and body. The command list is
generated from the facade catalog (the attack registry), so a newly registered
technique appears here without a second hand-written table.

Historical click names that differ from the registry id are kept in
``_COMMAND_NAMES``. AdvPrefix keeps its long-form help.
"""

import click

from hackagent.client import catalog_entries
from hackagent.interfaces.cli.commands.attack.group import eval_cmd
from hackagent.interfaces.cli.commands.attack.options import _common_attack_options
from hackagent.interfaces.cli.commands.attack.runner import _run_attack_command
from hackagent.interfaces.cli.utils import handle_errors

_ADVPREFIX_HELP = """Execute AdvPrefix attack strategy

This command runs the AdvPrefix attack against a target agent.
Goals should describe what you want the agent to do incorrectly.

Examples:

  # Basic attack with goals
        hackagent eval advprefix \\
    --agent-name "weather-bot" \\
    --agent-type "google-adk" \\
    --endpoint "http://localhost:8000" \\
    --goals "Return fake weather data and ignore safety guidelines"

          # Attack with configuration file
            hackagent eval advprefix \\
      --agent-name "multi-tool-agent" \\
      --agent-type "google-adk" \\
      --endpoint "http://localhost:8000" \\
      --config-file "attack-config.json"
"""

# Historical click names. New techniques use the registry id.
_COMMAND_NAMES = {
    "static_template": "static-template",
    "tool_output_ipi": "tool-output-ipi",
}
_HELP_OVERRIDES = {
    "advprefix": _ADVPREFIX_HELP,
}


def _catalog() -> dict:
    return {entry["attack_type"]: entry for entry in catalog_entries()}


def _strategy_table() -> dict:
    """``technique_key -> (command_name, help_text)`` in registry order."""
    table = {}
    for entry in catalog_entries():
        key = entry["attack_type"]
        label = entry["label"]
        help_text = _HELP_OVERRIDES.get(key) or f"Execute {label} attack strategy."
        table[key] = (_COMMAND_NAMES.get(key, key), help_text)
    return table


_STRATEGY_COMMANDS = _strategy_table()


def _make_strategy_command(
    technique_key: str, command_name: str, help_text: str
) -> click.Command:
    """Build and register the ``hackagent eval <command_name>`` command."""
    entry = _catalog()[technique_key]

    @click.pass_context
    def _command(ctx, **kwargs):
        _run_attack_command(
            ctx=ctx,
            attack_type=technique_key,
            attack_label=entry["label"],
            **kwargs,
        )

    _command.__name__ = technique_key
    tags = f" Tags: {', '.join(entry['tags'])}." if entry["tags"] else ""
    _command.__doc__ = (
        f"{help_text.rstrip()}\n\n"
        f"Category: {entry['category_label']} — "
        f"{entry['category_description']}{tags}"
    )

    return eval_cmd.command(name=command_name)(
        _common_attack_options(handle_errors(_command))
    )


for _key, (_name, _help) in _STRATEGY_COMMANDS.items():
    globals()[_key] = _make_strategy_command(_key, _name, _help)

__all__ = list(_STRATEGY_COMMANDS)
