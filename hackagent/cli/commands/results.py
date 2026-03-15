# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0


"""
Results Commands

View and manage attack results.
"""

from datetime import datetime

import click
from rich.console import Console
from rich.table import Table

from hackagent.cli.config import CLIConfig
from hackagent.cli.utils import handle_errors, launch_tui

console = Console()


@click.group()
def results():
    """📊 View and manage attack results"""
    # Show logo when results commands are used
    _show_logo_once()


def _show_logo_once():
    """Show the logo once per session"""
    if not hasattr(_show_logo_once, "_shown"):
        from hackagent.utils import display_hackagent_splash

        display_hackagent_splash()
        _show_logo_once._shown = True


@results.command()
@click.option("--limit", default=10, help="Number of results to show")
@click.option(
    "--status",
    type=click.Choice(["pending", "running", "completed", "failed"]),
    help="Filter by status",
)
@click.option("--agent", help="Filter by agent name")
@click.option("--attack-type", help="Filter by attack type")
@click.pass_context
@handle_errors
def list(ctx, limit, status, agent, attack_type):
    """List recent attack results"""
    cli_config: CLIConfig = ctx.obj["config"]
    cli_config.validate()
    launch_tui(cli_config, initial_tab="results")


@results.command()
@click.argument("result_id")
@click.pass_context
@handle_errors
def show(ctx, result_id):
    """Show detailed information about a specific result"""

    cli_config: CLIConfig = ctx.obj["config"]
    cli_config.validate()

    try:
        if cli_config.api_key:
            from hackagent.server.api.result import result_retrieve
            from hackagent.server.client import AuthenticatedClient

            client = AuthenticatedClient(
                base_url=cli_config.base_url, token=cli_config.api_key, prefix="Bearer"
            )

            with console.status(f"[bold green]Fetching result {result_id}..."):
                response = result_retrieve.sync_detailed(client=client, id=result_id)

            if response.status_code == 200 and response.parsed:
                result = response.parsed
            else:
                raise click.ClickException(f"Result not found: {result_id}")
        else:
            from uuid import UUID

            from hackagent.server.storage.local import LocalBackend

            backend = LocalBackend()
            with console.status(f"[bold green]Fetching result {result_id}..."):
                result = backend.get_result(UUID(result_id))

        _display_result_details(result)

    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Failed to fetch result: {e}")


def _display_result_details(result) -> None:
    """Display detailed information about a result"""

    # Basic info table
    table = Table(title="Result Details", show_header=True, header_style="bold cyan")
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("ID", str(result.id))

    if hasattr(result, "agent_name"):
        table.add_row("Agent", result.agent_name)

    if hasattr(result, "attack_type"):
        table.add_row("Attack Type", result.attack_type)

    if hasattr(result, "evaluation_status"):
        status = result.evaluation_status
        if hasattr(status, "value"):
            status = status.value
        table.add_row("Status", str(status))

    # Format dates
    if hasattr(result, "created_at") and result.created_at:
        try:
            if isinstance(result.created_at, datetime):
                created = result.created_at.strftime("%Y-%m-%d %H:%M:%S")
            else:
                created = str(result.created_at)
        except (AttributeError, ValueError, TypeError):
            created = str(result.created_at)
        table.add_row("Created", created)

    console.print(table)

    # Show additional data if available
    if hasattr(result, "data") and result.data:
        console.print("\n[bold cyan]📋 Result Data:")
        try:
            import json

            if isinstance(result.data, dict):
                data_str = json.dumps(result.data, indent=2)
            else:
                data_str = str(result.data)
            console.print(f"[dim]{data_str}")
        except (json.JSONDecodeError, TypeError, AttributeError):
            console.print(f"[dim]{result.data}")


@results.command()
@click.option(
    "--status",
    type=click.Choice(["pending", "running", "completed", "failed"]),
    help="Filter by status",
)
@click.option("--agent", help="Filter by agent name")
@click.option("--attack-type", help="Filter by attack type")
@click.option("--days", default=7, help="Number of days to include (default: 7)")
@click.pass_context
@handle_errors
def summary(ctx, status, agent, attack_type, days):
    """Show summary statistics of attack results"""

    cli_config: CLIConfig = ctx.obj["config"]
    cli_config.validate()

    try:
        if cli_config.api_key:
            from hackagent.server.api.result import result_list
            from hackagent.server.client import AuthenticatedClient

            client = AuthenticatedClient(
                base_url=cli_config.base_url, token=cli_config.api_key, prefix="Bearer"
            )

            # Page through all results for statistics
            all_results = []
            page = 1
            with console.status("[bold green]Analyzing results..."):
                while True:
                    response = result_list.sync_detailed(client=client, page=page)
                    if response.status_code != 200 or not response.parsed:
                        if page == 1:
                            raise click.ClickException(
                                f"Failed to fetch results: Status {response.status_code}"
                            )
                        break
                    batch = response.parsed.results or []
                    all_results.extend(batch)
                    if not response.parsed.next:
                        break
                    page += 1

            # Normalise remote result objects into simple attribute-compatible dicts
            # (they already have the needed attributes; kept as-is)
            result_items = all_results

        else:
            # Local mode — query SQLite directly
            from hackagent.server.storage.local import LocalBackend

            backend = LocalBackend()
            result_items = []
            page = 1
            with console.status("[bold green]Analyzing local results..."):
                while True:
                    page_data = backend.list_results(page=page, page_size=200)
                    result_items.extend(page_data.items)
                    if len(result_items) >= page_data.total:
                        break
                    page += 1

        # Filter by date range
        from datetime import datetime, timedelta

        cutoff_date = datetime.now() - timedelta(days=days)

        filtered_results = []
        for result in result_items:
            if hasattr(result, "created_at") and result.created_at:
                try:
                    created_date = result.created_at
                    if isinstance(created_date, str):
                        created_date = datetime.fromisoformat(
                            created_date.replace("Z", "+00:00")
                        )
                    if created_date >= cutoff_date:
                        filtered_results.append(result)
                except (ValueError, TypeError, AttributeError):
                    filtered_results.append(result)  # Include if date parsing fails
            else:
                filtered_results.append(result)

        # Apply status / agent / attack-type filters
        if status or agent or attack_type:
            temp_results = []
            for result in filtered_results:
                if status and hasattr(result, "evaluation_status"):
                    ev = result.evaluation_status
                    ev_val = ev.value if hasattr(ev, "value") else str(ev)
                    if status.upper() not in ev_val.upper():
                        continue
                if (
                    agent
                    and hasattr(result, "agent_name")
                    and agent.lower() not in result.agent_name.lower()
                ):
                    continue
                if (
                    attack_type
                    and hasattr(result, "attack_type")
                    and attack_type.lower() not in result.attack_type.lower()
                ):
                    continue
                temp_results.append(result)
            filtered_results = temp_results

        # Generate statistics
        stats = _generate_result_statistics(filtered_results, days)
        _display_result_summary(stats)

    except Exception as e:
        raise click.ClickException(f"Failed to generate summary: {e}")


def _generate_result_statistics(results, days: int) -> dict:
    """Generate statistics from results list"""
    total_results = len(results)

    # Count by status, agent, attack type
    status_counts = {}
    agent_counts = {}
    attack_counts = {}

    # For new metrics
    majority_vote_sum = 0.0
    fleiss_kappa_sum = 0.0
    metrics_count = 0  # Number of results with valid metrics

    for result in results:
        # Status statistics
        if hasattr(result, "evaluation_status"):
            status = result.evaluation_status
            if hasattr(status, "value"):
                status = status.value
            else:
                status = str(status)
            status_counts[status] = status_counts.get(status, 0) + 1

        # Agent statistics
        if hasattr(result, "agent_name"):
            agent = result.agent_name
            agent_counts[agent] = agent_counts.get(agent, 0) + 1

        # Attack type statistics
        if hasattr(result, "attack_type"):
            attack = result.attack_type
            attack_counts[attack] = attack_counts.get(attack, 0) + 1

        # Collect metrics if available
        if hasattr(result, "data") and result.data:
            data = result.data
            if "overall_majority_vote_asr" in data:
                majority_vote_sum += data["overall_majority_vote_asr"]
            if "overall_fleiss_kappa" in data:
                fleiss_kappa_sum += data["overall_fleiss_kappa"]
            metrics_count += 1

    # Compute averages
    avg_majority_vote_asr = (
        majority_vote_sum / metrics_count if metrics_count > 0 else 0.0
    )
    avg_fleiss_kappa = fleiss_kappa_sum / metrics_count if metrics_count > 0 else 0.0

    return {
        "period_days": days,
        "total_results": total_results,
        "status_breakdown": status_counts,
        "agent_breakdown": agent_counts,
        "attack_type_breakdown": attack_counts,
        "avg_majority_vote_asr": avg_majority_vote_asr,
        "avg_fleiss_kappa": avg_fleiss_kappa,
        "generated_at": str(datetime.now()),
    }


def _display_result_summary(stats: dict) -> None:
    """Display result statistics summary"""
    console.print(f"\n[bold cyan]📊 Results Summary (Last {stats['period_days']} days)")
    console.print(f"[green]Total Results: {stats['total_results']}")

    # Status breakdown
    if stats["status_breakdown"]:
        console.print("\n[bold cyan]📈 By Status:")
        status_table = Table(show_header=True, header_style="bold cyan")
        status_table.add_column("Status", style="cyan")
        status_table.add_column("Count", style="green")
        status_table.add_column("Percentage", style="yellow")

        for status, count in stats["status_breakdown"].items():
            percentage = (
                (count / stats["total_results"]) * 100
                if stats["total_results"] > 0
                else 0
            )
            status_table.add_row(status, str(count), f"{percentage:.1f}%")

        console.print(status_table)

    # Top agents
    if stats["agent_breakdown"]:
        console.print("\n[bold cyan]🤖 By Agent:")
        agent_table = Table(show_header=True, header_style="bold cyan")
        agent_table.add_column("Agent", style="cyan")
        agent_table.add_column("Count", style="green")

        # Sort by count and show top 5
        sorted_agents = sorted(
            stats["agent_breakdown"].items(), key=lambda x: x[1], reverse=True
        )
        for agent, count in sorted_agents[:5]:
            agent_table.add_row(agent, str(count))

        console.print(agent_table)

    # Attack types
    if stats["attack_type_breakdown"]:
        console.print("\n[bold cyan]🎯 By Attack Type:")
        attack_table = Table(show_header=True, header_style="bold cyan")
        attack_table.add_column("Attack Type", style="cyan")
        attack_table.add_column("Count", style="green")

        for attack_type, count in stats["attack_type_breakdown"].items():
            attack_table.add_row(attack_type, str(count))

        console.print(attack_table)

    # NEW: Show average metrics
    console.print("\n[bold cyan]📊 Average Evaluation Metrics Across Results:")
    metrics_table = Table(show_header=True, header_style="bold cyan")
    metrics_table.add_column("Metric", style="cyan")
    metrics_table.add_column("Average", style="green")

    metrics_table.add_row("Majority Vote ASR", f"{stats['avg_majority_vote_asr']:.3f}")
    metrics_table.add_row("Fleiss' Kappa", f"{stats['avg_fleiss_kappa']:.3f}")

    console.print(metrics_table)
