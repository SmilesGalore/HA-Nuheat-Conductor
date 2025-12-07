"""Nuheat Conductor integration with OAuth2 Authorization Code flow."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN

PLATFORMS = [Platform.CLIMATE]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

_LOGGER = logging.getLogger(__name__)

type NuheatConductorConfigEntry = ConfigEntry


async def async_setup_entry(
    hass: HomeAssistant, entry: NuheatConductorConfigEntry
) -> bool:
    """Set up Nuheat Conductor from a config entry."""
    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    )

    session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)

    # Verify we can get a valid token
    try:
        await session.async_ensure_token_valid()
    except Exception as err:
        _LOGGER.error("Failed to get valid token: %s", err)
        return False

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = session

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
