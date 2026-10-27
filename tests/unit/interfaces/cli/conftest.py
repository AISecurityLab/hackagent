"""CLI unit tests must not read the user's saved settings."""

import pytest


@pytest.fixture(autouse=True)
def isolated_default_settings(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "hackagent.core.settings.DEFAULT_CONFIG_PATH", tmp_path / "config.json"
    )
