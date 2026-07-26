# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Shared ``click`` options applied to every ``hackagent eval`` strategy."""

import click


def _common_attack_options(func):
    """Apply common CLI options shared by all attack subcommands."""
    options = [
        click.option("--agent-name", required=True, help="Target agent name"),
        click.option(
            "--agent-type",
            type=str,
            default="other",
            help="Agent type (e.g., google-adk, litellm, langchain, openai-sdk, mcp, a2a, or other)",
        ),
        click.option(
            "--endpoint",
            required=True,
            help="Agent endpoint URL. For OpenAI-compatible endpoints, provide base URL ending with /v1 (e.g., http://localhost:8000/v1). For LangServe, provide full path (e.g., http://localhost:8000/invoke).",
        ),
        click.option(
            "--goals",
            multiple=True,
            help="Attack goals. Repeat --goals multiple times or pass a comma-separated string.",
        ),
        click.option(
            "--config-file",
            type=click.Path(exists=True),
            help="Attack configuration file (JSON/YAML)",
        ),
        click.option("--timeout", default=300, help="Attack timeout in seconds"),
        click.option(
            "--dry-run",
            is_flag=True,
            help="Validate configuration without running attack",
        ),
        click.option(
            "--no-tui",
            is_flag=True,
            help="Run attack directly without opening TUI (default: open TUI)",
        ),
        # Before guardrail options
        click.option(
            "--before-guardrail-name",
            default=None,
            help="Before-guardrail model identifier (e.g., openai/gpt-oss-safeguard-20b)",
        ),
        click.option(
            "--before-guardrail-type",
            default=None,
            help="Before-guardrail agent type (e.g., openai-sdk, ollama)",
        ),
        click.option(
            "--before-guardrail-endpoint",
            default=None,
            help="Before-guardrail endpoint URL",
        ),
        # After guardrail options
        click.option(
            "--after-guardrail-name",
            default=None,
            help="After-guardrail model identifier (e.g., openai/gpt-oss-safeguard-20b)",
        ),
        click.option(
            "--after-guardrail-type",
            default=None,
            help="After-guardrail agent type (e.g., openai-sdk, ollama)",
        ),
        click.option(
            "--after-guardrail-endpoint",
            default=None,
            help="After-guardrail endpoint URL",
        ),
    ]

    for option in reversed(options):
        func = option(func)

    return func
