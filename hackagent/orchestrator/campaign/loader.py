"""Load declarative campaigns from YAML or already-decoded mappings."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import yaml

from hackagent.core.credentials import (
    REFERENCES_ONLY,
    prepare_credentials,
    validate_file_credentials,
)

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
            try:
                data = yaml.safe_load(stream)
            except yaml.YAMLError:
                raise ValueError("Could not parse campaign YAML.") from None
    if not isinstance(data, dict):
        raise ValueError("Campaign document must contain a YAML mapping.")
    return CampaignSpec.model_validate(
        prepare_credentials(data, from_file=not isinstance(source, Mapping))
    )


def load_stored_campaign(data: Mapping[str, Any]) -> CampaignSpec:
    """Validate a stored campaign, keeping its ``${VARIABLE}`` references.

    A key is read from its variable when the model that uses it is built, so
    the campaign can be checked where its variables are not set and executed
    where they are. Raises ``CredentialError`` for an ``api_key`` that is not
    a reference, without repeating its value.
    """
    validate_file_credentials(data)
    return CampaignSpec.model_validate(dict(data), context=REFERENCES_ONLY)


__all__ = ["load_campaign", "load_stored_campaign"]
