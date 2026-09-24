"""Nuheat Conductor integration with OAuth2 Authorization Code flow."""

from __future__ import annotations

import logging

from aiohttp import ClientError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers import config_validation as cv

from .auth import is_token_rejected
from .config_flow import NuheatConductorLocalOAuth2Implementation
from .const import DOMAIN
from .signalr import NuheatSignalRManager

PLATFORMS = [Platform.CLIMATE]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

_LOGGER = logging.getLogger(__name__)

type NuheatConductorConfigEntry = ConfigEntry


async def async_setup_entry(
    hass: HomeAssistant, entry: NuheatConductorConfigEntry
) -> bool:
    """Set up Nuheat Conductor from a config entry."""
    # Register the OAuth2 implementation
    # This is needed on restart since implementations aren't persisted
    config_entry_oauth2_flow.async_register_implementation(
        hass,
        DOMAIN,
        NuheatConductorLocalOAuth2Implementation(hass),
    )

    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    )

    session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)

    # Verify we can get a valid token
    try:
        await session.async_ensure_token_valid()
    except (ClientError, TimeoutError) as err:
        if is_token_rejected(err):
            # Refresh token expired/revoked: show "Re-authenticate" in the UI
            # instead of leaving the integration stuck in "Failed to set up".
            raise ConfigEntryAuthFailed(
                "Nuheat session expired, please re-authenticate"
            ) from err
        # Temporary problem (server error, no network): retry automatically.
        raise ConfigEntryNotReady(f"Unable to reach Nuheat: {err}") from err

    # Create and start the SignalR manager for real-time notifications
    signalr_manager = NuheatSignalRManager(hass, session)
    await signalr_manager.async_start()

    # Store both the session and SignalR manager for use by climate.py
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "session": session,
        "signalr": signalr_manager,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # Stop the SignalR connection cleanly before unloading
    entry_data = hass.data[DOMAIN].get(entry.entry_id, {})
    signalr_manager: NuheatSignalRManager | None = entry_data.get("signalr")
    if signalr_manager:
        await signalr_manager.async_stop()

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
