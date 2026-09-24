"""Tests for expired/revoked OAuth token handling (issue: silent 'Failed to set up')."""

from __future__ import annotations

import time

import pytest
from aiohttp import ClientResponseError
from unittest.mock import AsyncMock, MagicMock

from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.nuheat_conductor.climate import NuheatConductorAPI
from custom_components.nuheat_conductor.const import DOMAIN, TOKEN_URL
from custom_components.nuheat_conductor.signalr import NuheatSignalRManager


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Allow Home Assistant to load the custom integration under test."""
    yield


def _expired_entry() -> MockConfigEntry:
    """Return a config entry whose access token has expired."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOMAIN,
        title="Nuheat Conductor",
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "old-access",
                "refresh_token": "old-refresh",
                "token_type": "Bearer",
                "expires_in": 3600,
                "expires_at": time.time() - 3600,
            },
        },
    )


async def test_rejected_refresh_token_starts_reauth(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A 400 invalid_grant on refresh must surface a Re-authenticate prompt."""
    aioclient_mock.post(TOKEN_URL, status=400, json={"error": "invalid_grant"})
    entry = _expired_entry()
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR
    flows = list(entry.async_get_active_flows(hass, {SOURCE_REAUTH}))
    assert len(flows) == 1


async def test_temporary_server_error_retries_without_reauth(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A 5xx from NuHeat is transient: retry setup, do not ask the user to log in."""
    aioclient_mock.post(TOKEN_URL, status=503)
    entry = _expired_entry()
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert not list(entry.async_get_active_flows(hass, {SOURCE_REAUTH}))


async def test_reauth_flow_is_not_blocked_by_single_instance_check(
    hass: HomeAssistant,
) -> None:
    """Confirming re-authentication must proceed to NuHeat's login, not abort."""
    hass.config.components.add("my")  # provides the OAuth redirect URI
    entry = _expired_entry()
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    # Previously this aborted with "single_instance_allowed". In a real browser
    # HA auto-selects the only login method; without an HTTP request (as in
    # tests) it shows the picker, so choose it explicitly.
    assert result["type"] is FlowResultType.FORM, result
    assert result["step_id"] == "pick_implementation"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"implementation": DOMAIN}
    )
    assert result["type"] is FlowResultType.EXTERNAL_STEP, result
    assert "identity.nam.mynuheat.com/connect/authorize" in result["url"]


async def test_runtime_token_rejection_starts_reauth(hass: HomeAssistant) -> None:
    """If the login dies while running, the API client must ask for re-auth."""
    session = MagicMock()
    session.async_ensure_token_valid = AsyncMock(
        side_effect=ClientResponseError(MagicMock(), (), status=400)
    )
    api = NuheatConductorAPI(session, MagicMock())

    assert await api._make_request("GET", "/api/v1/Thermostat") is None
    session.config_entry.async_start_reauth.assert_called_once_with(session.hass)


async def test_signalr_stops_and_requests_reauth_when_token_rejected(
    hass: HomeAssistant,
) -> None:
    """SignalR must not retry a dead login forever (was 9,000+ silent retries)."""
    session = MagicMock()
    session.hass = hass
    session.async_ensure_token_valid = AsyncMock(
        side_effect=ClientResponseError(MagicMock(), (), status=400)
    )
    manager = NuheatSignalRManager(hass, session)

    await manager.async_start()
    await manager._task  # loop exits by itself instead of retrying

    session.config_entry.async_start_reauth.assert_called_once_with(hass)
    assert manager._running is False
