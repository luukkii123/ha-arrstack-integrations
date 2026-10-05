"""Each optional service must configure, recover and reject duplicates."""

from unittest.mock import AsyncMock

import pytest
from custom_components.arrstack.api import (
    ArrstackAuthError,
    ArrstackConnectionError,
    ArrstackError,
)
from custom_components.arrstack.config_flow import validate_connection
from pytest_homeassistant_custom_component.common import MockConfigEntry


@pytest.mark.parametrize("service", ["sonarr", "radarr", "sabnzbd", "seerr"])
@pytest.mark.parametrize(
    "failure,error",
    [
        (ArrstackAuthError("invalid"), "invalid_auth"),
        (ArrstackConnectionError("offline"), "cannot_connect"),
        (ArrstackError("invalid response"), "unexpected_response"),
    ],
)
async def test_service_error_then_success(hass, monkeypatch, service, failure, error):
    probe = AsyncMock(side_effect=failure)
    monkeypatch.setattr(
        "custom_components.arrstack.config_flow.validate_connection", probe
    )
    result = await hass.config_entries.flow.async_init(
        "arrstack", context={"source": "user"}
    )
    assert result["type"] == "menu"
    assert set(result["menu_options"]) == {"sonarr", "radarr", "sabnzbd", "seerr"}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": service}
    )
    assert result["step_id"] == service
    settings = {
        "url": "http://example.com/",
        "api_key": " example-key ",
        "scan_interval": 60,
        "verify_ssl": True,
    }
    result = await hass.config_entries.flow.async_configure(result["flow_id"], settings)
    assert result["errors"] == {"base": error}
    probe.side_effect = None
    probe.return_value = {"version": None}
    result = await hass.config_entries.flow.async_configure(result["flow_id"], settings)
    assert result["type"] == "create_entry"
    assert result["data"] == {
        "service": service,
        "url": "http://example.com",
        "api_key": "example-key",
        "scan_interval": 60,
        "verify_ssl": True,
    }
    assert result["result"].unique_id == f"{service}:http://example.com"


@pytest.mark.parametrize("service", ["sonarr", "radarr", "sabnzbd", "seerr"])
async def test_duplicate(hass, service):
    MockConfigEntry(
        domain="arrstack", unique_id=f"{service}:http://example.com", data={}
    ).add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        "arrstack", context={"source": "user"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": service}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"url": "http://example.com/", "api_key": "example-key"}
    )
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    "failure,error",
    [
        (ArrstackAuthError("invalid"), "invalid_auth"),
        (ArrstackConnectionError("offline"), "cannot_connect"),
        (ArrstackError("invalid response"), "unexpected_response"),
    ],
)
async def test_reauth_error_then_success(hass, monkeypatch, failure, error):
    probe = AsyncMock(side_effect=failure)
    monkeypatch.setattr(
        "custom_components.arrstack.config_flow.validate_connection", probe
    )
    monkeypatch.setattr(
        hass.config_entries, "async_reload", AsyncMock(return_value=True)
    )
    entry = MockConfigEntry(
        domain="arrstack",
        data={
            "service": "sonarr",
            "url": "http://example.com",
            "api_key": "example-old",
        },
        options={"api_key": "example-stale", "scan_interval": 120},
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        "arrstack",
        context={"source": "reauth", "entry_id": entry.entry_id},
        data=entry.data,
    )
    assert result["step_id"] == "reauth_confirm"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"api_key": "example-new"}
    )
    assert result["errors"] == {"base": error}
    probe.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"api_key": " example-new "}
    )
    assert result["reason"] == "reauth_successful"
    assert entry.data["api_key"] == "example-new"
    assert entry.options == {"scan_interval": 120}


@pytest.mark.parametrize(
    "token,want",
    [
        (" ", {"scan_interval": 120, "verify_ssl": False}),
        (
            " example-new ",
            {"api_key": "example-new", "scan_interval": 120, "verify_ssl": False},
        ),
    ],
)
async def test_options(hass, token, want):
    entry = MockConfigEntry(
        domain="arrstack",
        title="Example",
        data={
            "service": "sonarr",
            "url": "http://example.com",
            "api_key": "example-old",
        },
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["step_id"] == "init"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"api_key": token, "scan_interval": 120, "verify_ssl": False}
    )
    assert result["type"] == "create_entry"
    assert entry.options == want


@pytest.mark.parametrize(
    "service,result",
    [
        ("sabnzbd", {"version": "4.0"}),
        ("seerr", {"version": "2.0"}),
        ("sonarr", {"version": "4.0", "url_base": "/sonarr"}),
    ],
)
async def test_validation_dispatch(hass, monkeypatch, service, result):
    monkeypatch.setattr(
        "custom_components.arrstack.config_flow.SabClient.version",
        AsyncMock(return_value="4.0"),
    )
    monkeypatch.setattr(
        "custom_components.arrstack.config_flow.SeerrClient.status",
        AsyncMock(return_value={"version": "2.0"}),
    )
    monkeypatch.setattr(
        "custom_components.arrstack.config_flow.ArrClient.system_status",
        AsyncMock(return_value={"version": "4.0", "urlBase": "/sonarr"}),
    )
    assert (
        await validate_connection(
            hass, service, "http://example.com", "example-key", True
        )
        == result
    )


async def test_validation_rejects_wrong_service(hass, monkeypatch):
    monkeypatch.setattr(
        "custom_components.arrstack.config_flow.ArrClient.system_status",
        AsyncMock(return_value={}),
    )
    with pytest.raises(ArrstackError):
        await validate_connection(
            hass, "sonarr", "http://example.com", "example-key", True
        )
