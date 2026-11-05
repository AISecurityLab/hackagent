"""Campaign unit tests resolve settings without reading a user's configuration."""

import pytest


@pytest.fixture(autouse=True)
def isolated_default_settings(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "hackagent.core.settings.DEFAULT_CONFIG_PATH", tmp_path / "config.json"
    )
