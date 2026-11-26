# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
HackAgent CLI Main Entry Point

Main command-line interface for HackAgent security testing toolkit.
"""

import os

import click
from rich.markup import escape
from rich.traceback import install

from hackagent._version import get_version
from hackagent.core.credentials import CredentialError
from hackagent.interfaces.cli.commands import (
    campaign as campaign_cmd,
    datasets as datasets_cmd,
    examples,
    results,
    run as run_cmd,
    web as web_cmd,
)
from hackagent.interfaces.cli.commands import config
from hackagent.interfaces.cli.bootstrap import (
    _launch_tui_default,
)
from hackagent.interfaces.cli.config import CLIConfig
from hackagent.interfaces.cli.help_page import _help_option_callback
from hackagent.interfaces.cli.logging_setup import (
    apply_verbosity,
    setup_package_logging,
)
from hackagent.interfaces.cli.safe_stdio import (
    configure_safe_stdio,
    install_on_click_command,
)
from hackagent.interfaces.brand import APP, QUICK_START
from hackagent.interfaces.cli.utils import (
    Failed,
    console,
    display_error,
    display_heading,
    display_hint,
    display_info,
    display_success,
    display_warning,
    handle_errors,
)

# Install rich traceback handler for better error display
install(show_locals=True)


class _CLIGroup(click.Group):
    """Apply subcommand storage overrides before resolving root settings."""

    def resolve_command(self, ctx, args):
        name, command, remaining = super().resolve_command(ctx, args)
        if name == "web":
            with command.make_context(
                name, list(remaining), parent=ctx, resilient_parsing=True
            ) as subcontext:
                if subcontext.params.get("force_local"):
                    ctx.params["backend"] = "local"
        return name, command, remaining


@click.group(
    cls=_CLIGroup,
    invoke_without_command=True,
    add_help_option=False,
    # -h as well as --help, on every command: Click hands these down.
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.option(
    "--help",
    "-h",
    is_flag=True,
    is_eager=True,
    expose_value=False,
    callback=_help_option_callback,
    help="Show this message and exit.",
)
@click.option(
    "--config-file", type=click.Path(), help="Configuration file path (JSON/YAML)"
)
@click.option(
    "--backend",
    type=click.Choice(["local", "remote"]),
    default=None,
    help="Storage backend (default: local, or HACKAGENT_BACKEND)",
)
@click.option(
    "--base-url",
    default=None,
    help="HackAgent API base URL (or set HACKAGENT_BASE_URL env var)",
)
@click.option(
    "--ca-bundle",
    default=None,
    type=click.Path(exists=True),
    help=(
        "CA bundle (PEM) trusted for the HackAgent API, e.g. a private CA "
        "(or set REQUESTS_CA_BUNDLE / SSL_CERT_FILE)"
    ),
)
@click.option(
    "--verbose",
    "-v",
    count=True,
    help=(
        "Say more: -v every model call, -vv other libraries' messages too, "
        "-vvv everything"
    ),
)
@click.version_option(version=get_version(), prog_name="hackagent")
@click.pass_context
def cli(ctx, config_file, backend, base_url, ca_bundle, verbose):
    ctx.ensure_object(dict)

    # Set debug mode based on environment variable
    if os.getenv("HACKAGENT_DEBUG"):
        os.environ["HACKAGENT_DEBUG"] = "1"

    # Initialize CLI configuration
    try:
        ctx.obj["config"] = CLIConfig(
            config_file=config_file,
            backend=backend,
            base_url=base_url,
            verbose=verbose,
            ca_bundle=ca_bundle,
        )
    except Exception as e:
        display_error(f"Configuration error: {e}")
        if isinstance(e, CredentialError):
            display_info(
                "Set HACKAGENT_API_KEY or correct the api_key reference "
                "in the configuration file."
            )
        ctx.exit(1)

    # The run's log from INFO by default; -v adds every model call, -vv other
    # libraries' messages, -vvv everything. A count given here or saved in
    # the configuration file sets what the terminal shows.
    config = ctx.obj["config"]
    apply_verbosity(config.verbose)

    # Launch TUI by default if no subcommand is provided
    if ctx.invoked_subcommand is None:
        _launch_tui_default(ctx)


@cli.command()
@click.pass_context
@handle_errors
def init(ctx):
    """Set up HackAgent for the first time.

    Asks where results are kept and how much the log says, and saves it.
    """
    from hackagent.interfaces.cli.banner import display_hackagent_splash

    display_hackagent_splash(console)

    cli_config: CLIConfig = ctx.obj["config"]

    if cli_config.default_config_path.exists():
        if not click.confirm("Configuration already exists. Overwrite?"):
            display_info("Setup cancelled")
            return
        # Reload config from file to get the latest saved values
        cli_config.reload()

    # Storage backend setup. API keys are never saved to the config file.
    display_heading("Where results are kept")
    console.print("  [accent]local[/accent]   on this machine (the default)")
    console.print(
        "  [accent]remote[/accent]  on the HackAgent platform; the API key is "
        "read from the HACKAGENT_API_KEY environment variable"
    )

    use_remote = click.confirm(
        "Use remote storage?",
        default=cli_config.backend == "remote",
    )
    cli_config.set_user_override("backend", "remote" if use_remote else "local")
    if use_remote and not cli_config.api_key:
        display_warning(
            "HACKAGENT_API_KEY is not set. Export it before running: "
            "remote storage fails without it."
        )

    from hackagent.interfaces.cli.config import MAX_VERBOSITY, VERBOSITY

    display_heading("How much the log says")
    for count, said in VERBOSITY.items():
        console.print(f"  {count}  {said}" + ("  (the default)" if not count else ""))
    verbose_level = click.prompt(
        "Verbosity", type=click.IntRange(0, MAX_VERBOSITY), default=cli_config.verbose
    )
    cli_config.set_user_override("verbose", verbose_level)

    try:
        cli_config.save()
        display_success("Configuration saved")

        display_heading("Graphviz, for FC-Attack")
        display_info(
            "Graphviz is needed only to draw FC-Attack's images. "
            "tFC-Attack does not need it."
        )

        try:
            from hackagent.client import ensure_graphviz

            existing_dot = ensure_graphviz(allow_download=False)
            if existing_dot:
                display_success(
                    f"Graphviz found [secondary]{escape(str(existing_dot))}[/secondary]"
                )
            elif click.confirm(
                "Graphviz not found. Download portable binaries now for FC-Attack?",
                default=True,
            ):
                dot_path = ensure_graphviz(allow_download=True)
                if dot_path:
                    display_success(
                        f"Graphviz ready [secondary]{escape(str(dot_path))}[/secondary]"
                    )
                else:
                    display_warning(
                        "Could not prepare Graphviz. tFC-Attack still works, "
                        "or set HACKAGENT_GRAPHVIZ_DOT later."
                    )
            else:
                display_info(
                    "Skipped. Set HACKAGENT_GRAPHVIZ_DOT, or run init again, "
                    "when you need FC-Attack."
                )
        except Exception as graphviz_exc:
            display_warning(
                f"Could not check for Graphviz: [secondary]{escape(str(graphviz_exc))}[/secondary]"
            )

        console.print()
        if cli_config.backend == "remote":
            display_success("Ready: results go to the HackAgent platform")
        else:
            display_success(
                "Ready: results stay on this machine "
                "[secondary](~/.local/share/hackagent/hackagent.db)[/secondary]"
            )
        _next_steps()

    except Exception as e:
        raise Failed(f"Setup failed: {e}") from e


def _next_steps() -> None:
    """The way through a first campaign, as ``hackagent --help`` shows it."""
    display_heading("Next")
    for what, command in (*QUICK_START, APP):
        display_hint(what, command)


@cli.command()
@click.pass_context
@handle_errors
def doctor(ctx):
    """Check the setup for common problems.

    Says what is missing, and how to fix it: what the terminal app's Setup
    screen shows.
    """
    from hackagent.interfaces.setup import report_markup, setup_report

    sections, verdict = setup_report(ctx.obj["config"])
    for line in report_markup(sections, verdict):
        console.print(line)


cli.add_command(campaign_cmd.campaign)
cli.add_command(datasets_cmd.datasets)
cli.add_command(examples.examples)
cli.add_command(results.results)
cli.add_command(run_cmd.run)
cli.add_command(web_cmd.web)


# Add command groups
cli.add_command(config.config)

# Cover Click eager options (--version, --help) and the console-script entry.
install_on_click_command(cli)


def main() -> None:
    """Process entry for the ``hackagent`` console script and frozen binary."""
    configure_safe_stdio()
    setup_package_logging()
    cli()


if __name__ == "__main__":
    main()
