"""Run a campaign against existing Ollama or OpenAI-compatible model servers.

A thin argparse front-end over the campaign library; the endpoint-override and
server-readiness logic lives in
:mod:`hackagent.orchestrator.campaign.overrides`, shared with the
``hackagent campaign`` CLI command.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence

from hackagent.interfaces.cli.logging_setup import (
    setup_package_logging,
    suppress_noisy_libraries,
)
from hackagent.orchestrator.campaign import (
    CampaignSpec,
    EndpointOverrides,
    ServerReadiness,
    apply_endpoint_overrides,
    load_campaign,
    run_campaign,
    summary,
    wait_for_servers,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("campaign", nargs="?", type=Path, default=Path("campaign.yaml"))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--ollama-endpoint")
    parser.add_argument(
        "--openai-endpoint",
        help="Override the target and judges sharing its OpenAI-compatible endpoint",
    )
    parser.add_argument(
        "--judge-endpoint", help="Override other OpenAI-compatible judge endpoints"
    )
    parser.add_argument(
        "--attacker-endpoint",
        "--decorator-endpoint",
        dest="attacker_endpoint",
        help="Override attack role models' OpenAI-compatible endpoint",
    )
    parser.add_argument("--output-directory", type=Path)
    parser.add_argument("--wait-for-ollama", type=float, default=0)
    parser.add_argument("--ollama-pid", type=int)
    parser.add_argument("--wait-for-server", type=float, default=0)
    parser.add_argument("--server-pid", type=int)
    parser.add_argument("--judge-server-pid", type=int)
    parser.add_argument("--attacker-server-pid", type=int)
    parser.add_argument("--concurrency", type=int)
    args = parser.parse_args(argv)
    if args.wait_for_ollama < 0 or args.wait_for_server < 0:
        parser.error("wait times must be nonnegative")
    if args.concurrency is not None and args.concurrency < 1:
        parser.error("--concurrency must be positive")

    values = load_campaign(args.campaign).model_dump(mode="json")
    try:
        apply_endpoint_overrides(
            values,
            EndpointOverrides(
                ollama=args.ollama_endpoint,
                openai=args.openai_endpoint,
                judge=args.judge_endpoint,
                attacker=args.attacker_endpoint,
            ),
        )
    except ValueError as exc:
        parser.error(str(exc))
    execution = values["execution"]
    if args.dry_run:
        execution["dry_run"] = True
    if args.output_directory:
        execution["output"]["directory"] = str(args.output_directory)
    if args.concurrency is not None:
        execution["concurrency"] = {
            "attack": args.concurrency,
            "target": args.concurrency,
            "judge": args.concurrency,
        }
    campaign = CampaignSpec.model_validate(values)

    setup_package_logging(default_level_str="INFO")
    suppress_noisy_libraries("httpx", "httpcore", "LiteLLM")
    if not campaign.execution.dry_run:
        try:
            wait_for_servers(
                values,
                ServerReadiness(
                    wait_for_ollama=args.wait_for_ollama,
                    ollama_pid=args.ollama_pid,
                    wait_for_server=args.wait_for_server,
                    server_pid=args.server_pid,
                    judge_server_pid=args.judge_server_pid,
                    attacker_server_pid=args.attacker_server_pid,
                ),
            )
        except ValueError as exc:
            parser.error(str(exc))

    def on_event(event: str, **payload: Any) -> None:
        print(json.dumps({"event": event, **payload}), flush=True)

    result = run_campaign(campaign, on_event=on_event)
    report = summary(result)
    report["output_directory"] = campaign.execution.output.directory
    print(json.dumps(report), flush=True)
    return 0 if report["succeeded"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
