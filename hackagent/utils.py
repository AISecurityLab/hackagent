# Copyright 2025 - AI4I. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
import logging
import os
from pathlib import Path
from typing import Optional, Union

from dotenv import find_dotenv, load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from hackagent.router.types import AgentTypeEnum

logger = logging.getLogger(__name__)


HACKAGENT = """
██╗  ██╗ █████╗  ██████╗██╗  ██╗ █████╗  ██████╗ ███████╗███╗   ██╗████████╗
██║  ██║██╔══██╗██╔════╝██║ ██╔╝██╔══██╗██╔════╝ ██╔════╝████╗  ██║╚══██╔══╝
███████║███████║██║     █████╔╝ ███████║██║  ███╗█████╗  ██╔██╗ ██║   ██║
██╔══██║██╔══██║██║     ██╔═██╗ ██╔══██║██║   ██║██╔══╝  ██║╚██╗██║   ██║
██║  ██║██║  ██║╚██████╗██║  ██╗██║  ██║╚██████╔╝███████╗██║ ╚████║   ██║
╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝  ╚═══╝   ╚═╝
"""


def display_hackagent_splash():
    """Displays the HackAgent splash screen using the pre-defined ASCII art."""
    console = Console()

    # Create a Text object from the HACKAGENT string
    title_content = Text(HACKAGENT, style="bold dark_red")

    splash_panel = Panel(
        title_content,
        border_style="red",
        padding=(2, 2),
        expand=False,
    )

    console.print(splash_panel)
    console.print()


def resolve_agent_type(agent_type_input: Union[AgentTypeEnum, str]) -> AgentTypeEnum:
    """Resolves the agent type from a string or AgentTypeEnum member."""
    if isinstance(agent_type_input, str):
        try:
            # Convert to uppercase and replace hyphens with underscores for enum matching
            return AgentTypeEnum[agent_type_input.upper().replace("-", "_")]
        except KeyError:
            logger.warning(
                f"Invalid agent_type string: '{agent_type_input}'. Falling back to UNKNOWN. "
                f"Valid types are: {[member.name for member in AgentTypeEnum]}"
            )
            return AgentTypeEnum.UNKNOWN
    elif isinstance(agent_type_input, AgentTypeEnum):
        return agent_type_input
    else:
        logger.warning(
            f"Invalid agent_type type: {type(agent_type_input)}. Falling back to UNKNOWN."
        )
        return AgentTypeEnum.UNKNOWN


def resolve_api_token(
    direct_api_key_param: Optional[str],
    env_file_path: Optional[str] = None,
    config_file_path: Optional[str] = None,
) -> str:
    """
    Resolves the API token with standardized priority order.

    Priority order:
    1. Direct api_key parameter (highest priority)
    2. Config file (~/.hackagent/config.json or specified path)
    3. Environment variable (HACKAGENT_API_KEY, with .env file support)
    4. Error if not found (lowest priority)

    Args:
        direct_api_key_param: API key provided directly as parameter
        env_file_path: Optional path to .env file to load environment variables from
        config_file_path: Optional path to config file (defaults to ~/.hackagent/config.json)

    Returns:
        str: The resolved API token

    Raises:
        ValueError: If no API token can be found from any source
    """
    # Priority 1: Direct parameter
    if direct_api_key_param is not None:
        logger.debug("Using API token provided directly via 'api_key' parameter.")
        return direct_api_key_param

    # Priority 2: Config file
    api_token_from_config = _load_api_key_from_config(config_file_path)
    if api_token_from_config:
        logger.debug("Using API token from config file.")
        return api_token_from_config

    # Priority 3: Environment variable (with .env file support)
    api_token_from_env = _load_api_key_from_env(env_file_path)
    if api_token_from_env:
        logger.debug("Using API token from HACKAGENT_API_KEY environment variable.")
        return api_token_from_env

    # Priority 4: Error - no token found
    error_message = (
        "API token not found from any source. Tried:\n"
        "1. Direct 'api_key' parameter\n"
        "2. Config file (~/.hackagent/config.json)\n"
        "3. HACKAGENT_API_KEY environment variable\n"
        "\nTo fix: Set HACKAGENT_API_KEY, create config file, or pass api_key directly."
    )
    raise ValueError(error_message)


def _load_api_key_from_config(config_file_path: Optional[str] = None) -> Optional[str]:
    """Load API key from config file with standardized logic."""
    try:
        if config_file_path:
            config_path = Path(config_file_path)
        else:
            config_path = Path.home() / ".hackagent" / "config.json"

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
        else:
            logger.debug(f"No api_key found in config file: {config_path}")
            return None

    except Exception as e:
        logger.warning(f"Error loading config file: {e}")
        return None


def _load_api_key_from_env(env_file_path: Optional[str] = None) -> Optional[str]:
    """Load API key from environment variables with .env file support."""
    try:
        # Load .env file if specified or found
        dotenv_to_load = env_file_path or find_dotenv(usecwd=True)

        if dotenv_to_load:
            logger.debug(f"Loading .env file from: {dotenv_to_load}")
            load_dotenv(dotenv_to_load)
        else:
            logger.debug("No .env file found to load.")

        api_token = os.getenv("HACKAGENT_API_KEY")
        if api_token:
            logger.debug("Found API key in HACKAGENT_API_KEY environment variable")
            return api_token
        else:
            logger.debug("HACKAGENT_API_KEY environment variable not set")
            return None

    except Exception as e:
        logger.warning(f"Error loading environment variables: {e}")
        return None
