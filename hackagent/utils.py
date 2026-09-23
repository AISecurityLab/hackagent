# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from typing import Union

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from hackagent.core.logging import get_logger
from hackagent.router.types import AgentTypeEnum

logger = get_logger(__name__)


HACKAGENT_BANNER = """
██╗  ██╗ █████╗  ██████╗██╗  ██╗ █████╗  ██████╗ ███████╗███╗   ██╗████████╗
██║  ██║██╔══██╗██╔════╝██║ ██╔╝██╔══██╗██╔════╝ ██╔════╝████╗  ██║╚══██╔══╝
███████║███████║██║     █████╔╝ ███████║██║  ███╗█████╗  ██╔██╗ ██║   ██║
██╔══██║██╔══██║██║     ██╔═██╗ ██╔══██║██║   ██║██╔══╝  ██║╚██╗██║   ██║
██║  ██║██║  ██║╚██████╗██║  ██╗██║  ██║╚██████╔╝███████╗██║ ╚████║   ██║
╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝  ╚═══╝   ╚═╝
"""


def display_hackagent_splash() -> None:
    """Display the HackAgent splash screen using the pre-defined ASCII art."""
    console = Console()
    title_content = Text(HACKAGENT_BANNER, style="bold dark_red")

    splash_panel = Panel(
        title_content,
        border_style="red",
        padding=(2, 2),
        expand=False,
    )

    console.print(splash_panel)
    console.print()


def resolve_agent_type(agent_type_input: Union[AgentTypeEnum, str]) -> AgentTypeEnum:
    """Resolve the agent type from a string or AgentTypeEnum member."""
    if isinstance(agent_type_input, str):
        try:
            return AgentTypeEnum[agent_type_input.upper().replace("-", "_")]
        except KeyError:
            # Fall back to value/alias resolution (AgentTypeEnum._missing_
            # handles shorthand such as "claude" → CLAUDE_CODE).
            try:
                return AgentTypeEnum(agent_type_input)
            except ValueError:
                pass
            logger.warning(
                f"Invalid agent_type string: '{agent_type_input}'. Falling back to UNKNOWN. "
                f"Valid types are: {[member.name for member in AgentTypeEnum]}"
            )
            return AgentTypeEnum.UNKNOWN

    if isinstance(agent_type_input, AgentTypeEnum):
        return agent_type_input

    logger.warning(
        f"Invalid agent_type type: {type(agent_type_input)}. Falling back to UNKNOWN."
    )
    return AgentTypeEnum.UNKNOWN
