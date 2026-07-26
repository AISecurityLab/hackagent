# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Per-strategy ``hackagent eval <strategy>`` commands.

Every strategy command shares the exact same options and body — only the
technique key, the command name and the help text differ. Rather than
repeating ~40 lines of boilerplate fourteen times, the commands are generated
from :data:`_STRATEGY_COMMANDS` by :func:`_make_strategy_command`.

To expose a new strategy, add an entry to :data:`_STRATEGY_COMMANDS` (and to
``ATTACK_CATALOG``).
"""

import click

from hackagent.cli.commands.attack.catalog import ATTACK_CATALOG
from hackagent.cli.commands.attack.group import eval_cmd
from hackagent.cli.commands.attack.options import _common_attack_options
from hackagent.cli.commands.attack.runner import _run_attack_command
from hackagent.cli.utils import handle_errors

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

# ``technique_key -> (command_name, help_text)``. The command names are the
# historical, user-visible ones and must not be changed lightly.
_STRATEGY_COMMANDS = {
    "advprefix": ("advprefix", _ADVPREFIX_HELP),
    "baseline": (
        "baseline",
        "Execute Baseline attack strategy (direct goal submission, no transform).",
    ),
    "static_template": ("static-template", "Execute Static Template attack strategy."),
    "pair": ("pair", "Execute PAIR attack strategy."),
    "flipattack": ("flipattack", "Execute FlipAttack strategy."),
    "tap": ("tap", "Execute TAP attack strategy."),
    "autodan_turbo": ("autodan_turbo", "Execute AutoDAN-Turbo attack strategy."),
    "bon": ("bon", "Execute BoN attack strategy."),
    "cipherchat": ("cipherchat", "Execute CipherChat attack strategy."),
    "h4rm3l": ("h4rm3l", "Execute h4rm3l attack strategy."),
    "pap": ("pap", "Execute PAP attack strategy."),
    "mml": ("mml", "Execute MML (Multi-Modal Linkage) attack strategy."),
    "fc": ("fc", "Execute FC-Attack strategy against a VLM."),
    "tfc": (
        "tfc",
        "Execute tFC-Attack (text-only flowchart) strategy against any LLM.",
    ),
}


def _make_strategy_command(
    technique_key: str, command_name: str, help_text: str
) -> click.Command:
    """Build and register the ``hackagent eval <command_name>`` command."""

    @click.pass_context
    def _command(ctx, **kwargs):
        _run_attack_command(
            ctx=ctx,
            attack_type=technique_key,
            attack_label=ATTACK_CATALOG[technique_key]["label"],
            **kwargs,
        )

    _command.__name__ = technique_key
    _command.__doc__ = help_text

    return eval_cmd.command(name=command_name)(
        _common_attack_options(handle_errors(_command))
    )


for _key, (_name, _help) in _STRATEGY_COMMANDS.items():
    globals()[_key] = _make_strategy_command(_key, _name, _help)

__all__ = list(_STRATEGY_COMMANDS)
