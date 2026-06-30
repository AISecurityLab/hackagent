# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import json
import os
from pathlib import Path
from typing import Optional, Union

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from hackagent.logger import get_logger
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

# Backward compatible alias used by older CLI/help code.
HACKAGENT = HACKAGENT_BANNER


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


def resolve_api_token(
    direct_api_key_param: Optional[str] = None,
    config_file_path: Optional[str] = None,
) -> Optional[str]:
    """Resolve API token with standardized priority order.

    Priority:
    1. direct api_key parameter
    2. HACKAGENT_API_KEY environment variable
    3. config file (~/.config/hackagent/config.json or specified path)
    4. None => local mode
    """
    if direct_api_key_param is not None:
        logger.debug("Using API token provided directly via 'api_key' parameter.")
        return direct_api_key_param

    api_token_from_env = os.environ.get("HACKAGENT_API_KEY")
    if api_token_from_env:
        logger.debug("Using API token from HACKAGENT_API_KEY environment variable.")
        return api_token_from_env

    api_token_from_config = _load_api_key_from_config(config_file_path)
    if api_token_from_config:
        logger.debug("Using API token from config file.")
        return api_token_from_config

    logger.info(
        "No API key found. HackAgent running in local mode; "
        "results will be stored in ~/.local/share/hackagent/hackagent.db. "
        "Set HACKAGENT_API_KEY or pass api_key= to enable remote tracking."
    )
    return None


def _load_api_key_from_config(config_file_path: Optional[str] = None) -> Optional[str]:
    """Load API key from config file with standardized logic."""
    try:
        if config_file_path:
            config_path = Path(config_file_path)
        else:
            config_path = Path.home() / ".config" / "hackagent" / "config.json"

        if not config_path.exists():
            logger.debug(f"Config file not found at: {config_path}")
            return None

        logger.debug(f"Loading config from: {config_path}")

        with open(config_path) as f:
            if config_path.suffix.lower() in [".yaml", ".yml"]:
                try:
                    import yaml

                    config_data = yaml.safe_load(f)
                except ImportError:
                    logger.warning("PyYAML not available, cannot load YAML config file")
                    return None
            else:
                config_data = json.load(f)

        api_key = config_data.get("api_key")
        if api_key:
            logger.debug(f"Found API key in config file: {config_path}")
            return api_key

        logger.debug(f"No api_key found in config file: {config_path}")
        return None
    except Exception as e:
        logger.warning(f"Error loading config file: {e}")
        return None
