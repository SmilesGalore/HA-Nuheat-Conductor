"""Nuheat Conductor Thermostat Climate Platform for Home Assistant."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Mapping
from datetime import timedelta
from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import API_URL, DOMAIN

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=5)


class NuheatConductorAPI:
    """API client for Nuheat Conductor thermostats using OAuth2 session."""

    def __init__(
        self,
        session: config_entry_oauth2_flow.OAuth2Session,
        websession,
    ) -> None:
        """Initialize the API client."""
        self._oauth_session = session
        self._websession = websession

    async def _get_access_token(self) -> str:
        """Get a valid access token."""
        await self._oauth_session.async_ensure_token_valid()
        return self._oauth_session.token["access_token"]

    async def _make_request(
        self, method: str, endpoint: str, **kwargs: Any
    ) -> dict | list | None:
        """Make an authenticated API request."""
        try:
            access_token = await self._get_access_token()
        except Exception:
            _LOGGER.exception("Failed to get access token")
            return None

        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {access_token}"
        headers["Accept"] = "application/json"

        url = f"{API_URL}{endpoint}"

        try:
            async with (
                asyncio.timeout(10),
                self._websession.request(
                    method, url, headers=headers, **kwargs
                ) as resp,
            ):
                if resp.status == 401:
                    _LOGGER.warning("Received 401, token may be invalid")
                    return None
                if resp.status == 200:
                    return await resp.json()
                _LOGGER.error("Request to %s failed: %s", endpoint, resp.status)
                return None
        except TimeoutError:
            _LOGGER.error("Timeout during request to %s", endpoint)
            return None
        except Exception:
            _LOGGER.exception("Error during request to %s", endpoint)
            return None

    async def get_thermostats(self) -> list[Any]:
        """Get list of thermostats."""
        data = await self._make_request("GET", "/api/v2/Thermostats")
        if isinstance(data, list):
            return data
        return []

    async def get_thermostat_data(self, thermostat_id: str) -> dict | None:
        """Get data for a specific thermostat."""
        data = await self._make_request("GET", f"/api/v2/Thermostat/{thermostat_id}")
        if isinstance(data, dict):
            return data
        return None

    async def set_target_temperature(
        self, thermostat_id: str, temperature: float, mode: int = 3
    ) -> bool:
        """Set target temperature for a thermostat.

        Args:
            thermostat_id: The thermostat serial number
            temperature: Target temperature in Fahrenheit
            mode: Schedule mode (1=schedule, 2=temporary hold, 3=permanent hold)

        """
        data = {"setPointTemp": temperature, "scheduleMode": mode}
        result = await self._make_request(
            "PUT", f"/api/v2/Thermostat/{thermostat_id}", json=data
        )
        return result is not None

    async def set_schedule_mode(self, thermostat_id: str, mode: int) -> bool:
        """Set the schedule mode for a thermostat."""
        data = {"scheduleMode": mode}
        result = await self._make_request(
            "PUT", f"/api/v2/Thermostat/{thermostat_id}", json=data
        )
        return result is not None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Nuheat Conductor climate platform from config entry."""
    oauth_session = hass.data[DOMAIN][entry.entry_id]
    websession = async_get_clientsession(hass)

    api = NuheatConductorAPI(oauth_session, websession)

    try:
        thermostats = await api.get_thermostats()
        _LOGGER.debug("Found %d thermostats", len(thermostats))

        entities = [
            NuheatConductorThermostat(api, thermostat, entry.entry_id)
            for thermostat in thermostats
        ]
        async_add_entities(entities, True)
    except Exception:
        _LOGGER.exception("Failed to get thermostats")


class NuheatConductorThermostat(ClimateEntity):
    """Representation of a Nuheat Conductor thermostat."""

    _attr_has_entity_name = True
    _attr_temperature_unit = UnitOfTemperature.FAHRENHEIT
    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.AUTO, HVACMode.OFF]
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE

    def __init__(
        self, api: NuheatConductorAPI, thermostat_data: dict, entry_id: str
    ) -> None:
        """Initialize the thermostat."""
        self._api = api
        self._thermostat_id: str = thermostat_data.get("serialNumber", "")
        self._attr_name = thermostat_data.get("name", "Nuheat Conductor Thermostat")
        self._attr_unique_id = f"nuheat_conductor_{self._thermostat_id}"
        self._current_temperature: float | None = None
        self._target_temperature: float | None = None
        self._min_temperature: float | None = None
        self._max_temperature: float | None = None
        self._schedule_mode: int | None = None
        self._is_heating = False
        self._is_online = True
        self._attr_available = True

        # Set initial values from thermostat data
        self._update_from_data(thermostat_data)

    def _update_from_data(self, data: dict) -> None:
        """Update internal state from thermostat data."""
        if not data:
            return
        self._current_temperature = data.get("temperature")
        self._target_temperature = data.get("setPointTemp")
        self._min_temperature = data.get("minTemp")
        self._max_temperature = data.get("maxTemp")
        self._schedule_mode = data.get("scheduleMode")
        self._is_heating = data.get("heating", False)
        self._is_online = data.get("online", True)

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self._current_temperature

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        return self._target_temperature

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        return self._min_temperature or 41.0

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        return self._max_temperature or 104.0

    @property
    def hvac_mode(self) -> HVACMode:
        """Return current HVAC mode."""
        if not self._is_online:
            return HVACMode.OFF
        if self._schedule_mode == 1:
            return HVACMode.AUTO
        return HVACMode.HEAT

    @property
    def hvac_action(self) -> HVACAction:
        """Return current HVAC action."""
        if not self._is_online:
            return HVACAction.OFF
        if self._is_heating:
            return HVACAction.HEATING
        return HVACAction.IDLE

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return additional state attributes."""
        attrs: dict[str, Any] = {}
        if self._schedule_mode:
            mode_names = {1: "Schedule", 2: "Temporary Hold", 3: "Permanent Hold"}
            attrs["schedule_mode"] = mode_names.get(self._schedule_mode, "Unknown")
        return attrs

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temperature = kwargs.get("temperature")
        if temperature is None or not self._thermostat_id:
            return

        success = await self._api.set_target_temperature(
            self._thermostat_id, temperature, mode=3
        )
        if success:
            self._target_temperature = temperature
            self._schedule_mode = 3
            self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set HVAC mode."""
        if not self._thermostat_id:
            return

        if hvac_mode == HVACMode.AUTO:
            success = await self._api.set_schedule_mode(self._thermostat_id, 1)
            if success:
                self._schedule_mode = 1
                self.async_write_ha_state()
        elif hvac_mode == HVACMode.HEAT:
            if self._target_temperature:
                await self.async_set_temperature(temperature=self._target_temperature)
        elif hvac_mode == HVACMode.OFF:
            await self.async_set_temperature(temperature=self.min_temp)

    async def async_update(self) -> None:
        """Update thermostat data."""
        if not self._thermostat_id:
            return

        data = await self._api.get_thermostat_data(self._thermostat_id)
        if data:
            self._update_from_data(data)
            self._attr_available = True
        else:
            self._attr_available = False
