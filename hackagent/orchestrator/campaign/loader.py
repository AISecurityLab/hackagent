"""Load declarative campaigns from YAML or already-decoded mappings."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import yaml

from hackagent.orchestrator.campaign.spec import CampaignSpec


def load_campaign(source: str | Path | Mapping[str, Any]) -> CampaignSpec:
    """Validate and return one campaign specification."""
    if isinstance(source, Mapping):
        data = dict(source)
    else:
        path = Path(source).expanduser()
        if not path.is_file():
            raise FileNotFoundError(f"Campaign file does not exist: {path}")
        with path.open("r", encoding="utf-8") as stream:
            data = yaml.safe_load(stream)
    if not isinstance(data, dict):
        raise ValueError("Campaign document must contain a YAML mapping.")
    return CampaignSpec.model_validate(data)


__all__ = ["load_campaign"]
