"""Run real HA flow managers, with setup and external I/O isolated."""

import sys
from pathlib import Path
from unittest.mock import AsyncMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pytest

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(autouse=True)
def enable_custom(enable_custom_integrations):
    yield


@pytest.fixture(autouse=True)
def isolate_entry_setup(monkeypatch):
    monkeypatch.setattr(
        "custom_components.arrstack.async_setup_entry", AsyncMock(return_value=True)
    )
    monkeypatch.setattr(
        "custom_components.arrstack.async_unload_entry", AsyncMock(return_value=True)
    )
