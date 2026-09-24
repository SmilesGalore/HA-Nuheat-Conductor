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
from .auth import is_token_rejected, start_reauth
from .signalr import NuheatSignalRManager

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=90)


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
        except Exception as err:
            if is_token_rejected(err):
                _LOGGER.error(
                    "Nuheat rejected the saved login (%s); re-authentication required",
                    err,
                )
                start_reauth(self._oauth_session)
            else:
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
                if resp.status == 204:
                    # 204 No Content - success with no body (common for PUT/POST)
                    return {}
                # Log detailed error information for non-success responses
                error_body = await resp.text()
                _LOGGER.error(
                    "Request to %s failed: %s - Response: %s",
                    endpoint,
                    resp.status,
                    error_body,
                )
                return None
        except TimeoutError:
            _LOGGER.error("Timeout during request to %s", endpoint)
            return None
        except Exception:
            _LOGGER.exception("Error during request to %s", endpoint)
            return None

    async def get_thermostats(self) -> list[Any]:
        """Get list of thermostats."""
        data = await self._make_request("GET", "/api/v1/Thermostat")
        if isinstance(data, list):
            return data
        return []

    async def get_groups(self) -> list[Any]:
        """Get list of thermostat groups."""
        data = await self._make_request("GET", "/api/v1/Group")
        if isinstance(data, list):
            return data
        return []

    async def set_group_away_mode(self, group_id: str, away_mode: bool) -> bool:
        """Set away mode for a group.

        Args:
            group_id: The group ID
            away_mode: True to enable away mode, False to disable

        """
        data = {"groupId": group_id, "awayMode": away_mode}
        _LOGGER.debug("Setting group away mode: %s", data)
        result = await self._make_request("PUT", "/api/v1/Group", json=data)
        return result is not None

    async def get_account_info(self) -> dict | None:
        """Get account information including temperature scale preference."""
        data = await self._make_request("GET", "/api/v1/Account")
        if isinstance(data, dict):
            return data
        return None

    async def get_thermostat_data(self, thermostat_id: str) -> dict | None:
        """Get data for a specific thermostat."""
        data = await self._make_request("GET", f"/api/v1/Thermostat/{thermostat_id}")
        if isinstance(data, dict):
            return data
        return None

    async def set_target_temperature(
        self, thermostat_id: str, temperature: float, name: str = "", mode: int = 2
    ) -> bool:
        """Set target temperature for a thermostat.

        Args:
            thermostat_id: The thermostat serial number
            temperature: Target temperature in user's preferred unit (Celsius or Fahrenheit)
            name: The thermostat name
            mode: Schedule mode (1=schedule, 2=temporary hold, 3=permanent hold)

        """
        # Convert temperature to integer format (30.0 = 3000)
        temp_int = int(temperature * 100)
        _LOGGER.debug(
            "API set_target_temperature: temp_float=%s, temp_int=%s, mode=%s",
            temperature,
            temp_int,
            mode,
        )
        # Include all fields from the API schema
        data = {
            "serialNumber": thermostat_id,
            "name": name,
            "setPointTemp": temp_int,
            "scheduleMode": mode,
            "holdSetPointDateTime": None,  # null for temporary/permanent hold
        }
        _LOGGER.debug("Sending to API: %s", data)
        result = await self._make_request("PUT", "/api/v1/Thermostat", json=data)
        return result is not None

    async def set_schedule_mode(
        self,
        thermostat_id: str,
        mode: int,
        name: str = "",
        current_temp: float | None = None,
    ) -> bool:
        """Set the schedule mode for a thermostat.

        When switching to Hold or Permanent Hold, the current setpoint must be
        included in the payload or the API may reset the temperature to 0.
        """
        data: dict = {"serialNumber": thermostat_id, "scheduleMode": mode}
        if name:
            data["name"] = name
        # Always include the setpoint when switching to Hold or Permanent Hold
        # to prevent the API from resetting the temperature to 0
        if current_temp is not None and mode in (2, 3):
            data["setPointTemp"] = int(current_temp * 100)
            data["holdSetPointDateTime"] = None
        _LOGGER.debug("Setting schedule mode: %s", data)
        result = await self._make_request("PUT", "/api/v1/Thermostat", json=data)
        return result is not None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Nuheat Conductor climate platform from config entry."""
    entry_data = hass.data[DOMAIN][entry.entry_id]
    oauth_session = entry_data["session"]
    signalr_manager: NuheatSignalRManager = entry_data["signalr"]
    websession = async_get_clientsession(hass)

    api = NuheatConductorAPI(oauth_session, websession)

    try:
        # Get account info to determine user preferences (e.g. clock format).
        # Note: the Nuheat API always returns raw temperature values in Celsius,
        # regardless of the account's "temperatureScale" display preference (that
        # preference only affects the Nuheat app's own UI). Home Assistant is told
        # the native unit is Celsius so it can convert to the user's configured
        # display unit automatically.
        account_info = await api.get_account_info()
        temp_scale = UnitOfTemperature.CELSIUS
        use_12_hour = True  # Default to 12-hour clock

        if account_info:
            use_12_hour = account_info.get("use12Hour", True)
            _LOGGER.debug(
                "Account preferences - temperature scale: %s, use 12-hour: %s",
                account_info.get("temperatureScale"),
                use_12_hour,
            )

        # Get thermostats
        thermostats = await api.get_thermostats()
        _LOGGER.debug("Found %d thermostats", len(thermostats))
        if not thermostats:
            _LOGGER.warning(
                "No thermostats returned from API — check account credentials "
                "and that thermostats are visible in the Nuheat app"
            )

        # Get groups
        groups = await api.get_groups()
        _LOGGER.debug("Found %d groups", len(groups))

        # Create thermostat entities
        entities = [
            NuheatConductorThermostat(
                api,
                thermostat,
                entry.entry_id,
                temp_scale,
                use_12_hour,
                signalr_manager,
            )
            for thermostat in thermostats
        ]

        # Create group entities
        entities.extend(
            [
                NuheatConductorGroup(
                    api, group, entry.entry_id, temp_scale, use_12_hour, signalr_manager
                )
                for group in groups
            ]
        )

        async_add_entities(entities, True)
    except Exception:
        _LOGGER.exception("Failed to get thermostats and groups")


class NuheatConductorThermostat(ClimateEntity):
    """Representation of a Nuheat Conductor thermostat."""

    _attr_has_entity_name = True
    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
    _attr_preset_modes = ["Auto", "Hold", "Permanent Hold"]
    # Don't set _attr_supported_features as static - use property instead
    # so we can disable controls when offline

    def __init__(
        self,
        api: NuheatConductorAPI,
        thermostat_data: dict,
        entry_id: str,
        temperature_unit: UnitOfTemperature,
        use_12_hour: bool = True,
        signalr_manager: NuheatSignalRManager | None = None,
    ) -> None:
        """Initialize the thermostat."""
        self._api = api
        self._thermostat_id: str = thermostat_data.get("serialNumber", "")
        self._attr_name = thermostat_data.get("name", "Nuheat Conductor Thermostat")
        self._attr_unique_id = f"nuheat_conductor_{self._thermostat_id}"
        self._attr_temperature_unit = temperature_unit
        self._use_12_hour = use_12_hour
        self._signalr_manager = signalr_manager
        self._current_temperature: float | None = None
        self._target_temperature: float | None = None
        self._min_temperature: float | None = None
        self._max_temperature: float | None = None
        self._schedule_mode: int | None = None
        self._is_heating = False
        self._is_online = True
        self._attr_available = True
        self._consecutive_failures = 0  # Track API failures before marking unavailable

        # Set initial values from thermostat data
        self._update_from_data(thermostat_data)

    async def async_added_to_hass(self) -> None:
        """Register SignalR callback when entity is added to HA."""
        if self._signalr_manager and self._thermostat_id:
            self._signalr_manager.register_callback(
                self._thermostat_id, self._async_signalr_update
            )
            _LOGGER.debug(
                "Registered SignalR callback for thermostat %s", self._thermostat_id
            )

    async def async_will_remove_from_hass(self) -> None:
        """Unregister SignalR callback when entity is removed."""
        if self._signalr_manager and self._thermostat_id:
            self._signalr_manager.unregister_callback(self._thermostat_id)

    async def _async_signalr_update(self) -> None:
        """Handle a real-time SignalR notification by refreshing state from API."""
        _LOGGER.debug("SignalR triggered update for thermostat %s", self._thermostat_id)
        await self.async_update()
        self.async_write_ha_state()

    def _update_from_data(self, data: dict) -> None:
        """Update internal state from thermostat data."""
        if not data:
            return

        _LOGGER.debug("Raw thermostat data: %s", data)

        try:
            # Convert temperatures from integer (3000 = 30.00°C, 2195 = 21.95°C) to float
            # Thermostats only support 0.5° increments, so round to nearest 0.5
            # This also handles imprecise values the API sometimes returns (e.g. 2186, 2192)
            # which are artefacts of Fahrenheit/Celsius schedule conversions
            def convert_temp(raw: int) -> float:
                """Convert raw API temp integer to nearest 0.5 degree increment."""
                return round((raw / 100.0) * 2) / 2

            temp = data.get("currentTemperature")
            self._current_temperature = convert_temp(temp) if temp is not None else None
            _LOGGER.debug(
                "Temperature conversion for %s: raw=%s, converted=%s, unit=%s",
                self._attr_name,
                temp,
                self._current_temperature,
                self._attr_temperature_unit,
            )

            setpoint = data.get("setPointTemp")
            self._target_temperature = (
                convert_temp(setpoint) if setpoint is not None else None
            )

            min_temp = data.get("minTemp")
            self._min_temperature = (
                convert_temp(min_temp) if min_temp is not None else None
            )

            max_temp = data.get("maxTemp")
            self._max_temperature = (
                convert_temp(max_temp) if max_temp is not None else None
            )

            self._schedule_mode = data.get("scheduleMode")
            self._is_online = data.get("online", True)

            # If offline, override heating status to prevent showing active heating
            if not self._is_online:
                self._is_heating = False
            else:
                self._is_heating = data.get("isHeating", False)

        except Exception:
            _LOGGER.exception(
                "Error parsing thermostat data for %s: %s", self._attr_name, data
            )

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
        if self._min_temperature is not None:
            return self._min_temperature
        # Default based on temperature unit
        return 5.0 if self._attr_temperature_unit == UnitOfTemperature.CELSIUS else 41.0

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        if self._max_temperature is not None:
            return self._max_temperature
        # Default based on temperature unit
        return (
            40.0 if self._attr_temperature_unit == UnitOfTemperature.CELSIUS else 104.0
        )

    @property
    def hvac_mode(self) -> HVACMode:
        """Return current HVAC mode."""
        # Show as OFF when offline so UI clearly indicates no active control
        if not self._is_online:
            return HVACMode.OFF
        return HVACMode.HEAT

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode."""
        if self._schedule_mode == 1:
            return "Auto"
        elif self._schedule_mode == 2:
            return "Hold"
        elif self._schedule_mode == 3:
            return "Permanent Hold"
        return None

    @property
    def supported_features(self) -> ClimateEntityFeature:
        """Return the list of supported features.

        Always return full features even when offline. The offline guard lives
        inside async_set_temperature and async_set_preset_mode. Returning no
        features when offline causes HA automations to throw 'does not support
        action' errors and abort, preventing other thermostats in the same
        automation call from being updated.
        """
        return (
            ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE
        )

    @property
    def hvac_action(self) -> HVACAction:
        """Return current HVAC action."""
        # Show OFF when offline (entity stays available to show settings)
        if not self._is_online:
            return HVACAction.OFF
        if self._is_heating:
            return HVACAction.HEATING
        return HVACAction.IDLE

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return additional state attributes."""
        attrs: dict[str, Any] = {}

        # Show prominent online/offline status
        attrs["connection_status"] = "Online" if self._is_online else "Offline"

        # Add warning badge for offline thermostats
        if not self._is_online:
            attrs["warning"] = "Thermostat is offline - showing last known settings"

        return attrs

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temperature = kwargs.get("temperature")
        if temperature is None or not self._thermostat_id:
            return

        # Prevent changes when thermostat is offline
        if not self._is_online:
            _LOGGER.warning(
                "Cannot set temperature for %s - thermostat is offline",
                self._attr_name,
            )
            return

        _LOGGER.debug(
            "Setting temperature for %s: received=%s, current_unit=%s",
            self._attr_name,
            temperature,
            self._attr_temperature_unit,
        )

        # Determine the correct scheduleMode to send:
        # - If currently on Auto (schedule mode 1): user is overriding schedule -> use Hold (2)
        # - If currently on Hold (2): keep it as Hold (2)
        # - If currently on Permanent Hold (3): keep it as Permanent Hold (3)
        # - If no schedule mode is known (None): default to Permanent Hold (3)
        #   because without a schedule, Hold (2) doesn't stick
        if self._schedule_mode == 1:
            # On a schedule - temporary override until next schedule event
            send_mode = 2  # Hold
        elif self._schedule_mode == 2:
            # Already in Hold - keep it as Hold
            send_mode = 2
        elif self._schedule_mode == 3:
            # In Permanent Hold - respect user's choice and keep as Permanent Hold
            send_mode = 3
        else:
            # Unknown/no schedule - use Permanent Hold so the change actually sticks
            send_mode = 3

        _LOGGER.debug(
            "Determined scheduleMode for %s: current_mode=%s, sending_mode=%s",
            self._attr_name,
            self._schedule_mode,
            send_mode,
        )

        success = await self._api.set_target_temperature(
            self._thermostat_id, temperature, name=self._attr_name, mode=send_mode
        )
        if success:
            self._schedule_mode = send_mode
            _LOGGER.debug("Temperature set command sent successfully")
            self.async_write_ha_state()
        else:
            # Failed to set temperature (likely thermostat is offline)
            # Refresh state from API to revert UI to actual values
            _LOGGER.warning(
                "Failed to set temperature for %s, reverting to actual state",
                self._attr_name,
            )
            await self.async_update()
            self.async_write_ha_state()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set preset mode."""
        if not self._thermostat_id:
            return

        # Prevent changes when thermostat is offline
        if not self._is_online:
            _LOGGER.warning(
                "Cannot set preset mode for %s - thermostat is offline",
                self._attr_name,
            )
            return

        # Map preset mode to schedule mode
        mode_map = {
            "Auto": 1,  # Schedule
            "Hold": 2,  # Temporary hold
            "Permanent Hold": 3,  # Permanent hold
        }

        mode = mode_map.get(preset_mode)
        if mode is None:
            _LOGGER.error("Unknown preset mode: %s", preset_mode)
            return

        success = await self._api.set_schedule_mode(
            self._thermostat_id,
            mode,
            name=self._attr_name,
            current_temp=self._target_temperature,
        )
        if success:
            self._schedule_mode = mode
            self.async_write_ha_state()
        else:
            _LOGGER.warning(
                "Failed to set preset mode for %s, reverting to actual state",
                self._attr_name,
            )
            await self.async_update()
            self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set HVAC mode."""
        if not self._thermostat_id:
            return

        # Prevent changes when thermostat is offline
        if not self._is_online:
            _LOGGER.warning(
                "Cannot set HVAC mode for %s - thermostat is offline",
                self._attr_name,
            )
            return

        # Map HVAC mode to a temperature change:
        # HEAT - restore to current target (or do nothing if already heating)
        # OFF  - set to minimum temperature as a soft off
        if hvac_mode == HVACMode.HEAT:
            if self._target_temperature is not None:
                await self.async_set_temperature(temperature=self._target_temperature)
        elif hvac_mode == HVACMode.OFF:
            await self.async_set_temperature(temperature=self.min_temp)

    async def async_update(self) -> None:
        """Update thermostat data."""
        if not self._thermostat_id:
            return

        data = await self._api.get_thermostat_data(self._thermostat_id)
        if data:
            self._consecutive_failures = 0
            self._update_from_data(data)
            self._attr_available = True
        else:
            self._consecutive_failures += 1
            # Only mark unavailable after 3 consecutive failures to avoid
            # flickering unavailable on transient network blips
            if self._consecutive_failures >= 3:
                _LOGGER.warning(
                    "%s marked unavailable after %d consecutive API failures",
                    self._attr_name,
                    self._consecutive_failures,
                )
                self._attr_available = False


class NuheatConductorGroup(ClimateEntity):
    """Representation of a Nuheat Conductor thermostat group."""

    _attr_has_entity_name = True
    _attr_hvac_modes = [HVACMode.HEAT]
    _attr_preset_modes = ["Home", "Away"]
    _attr_supported_features = ClimateEntityFeature.PRESET_MODE

    def __init__(
        self,
        api: NuheatConductorAPI,
        group_data: dict,
        entry_id: str,
        temperature_unit: UnitOfTemperature,
        use_12_hour: bool = True,
        signalr_manager: NuheatSignalRManager | None = None,
    ) -> None:
        """Initialize the group."""
        self._api = api
        self._group_id: str = group_data.get("groupId", "")
        group_name = group_data.get("groupName", "Nuheat Group")
        self._attr_name = f"Group: {group_name}"
        self._attr_unique_id = f"nuheat_conductor_group_{self._group_id}"
        self._attr_temperature_unit = temperature_unit
        self._use_12_hour = use_12_hour
        self._signalr_manager = signalr_manager
        self._away_mode: bool = False
        self._away_setpoint: float | None = None
        self._attr_available = True

        # Set initial values from group data
        self._update_from_data(group_data)

    async def async_added_to_hass(self) -> None:
        """Register SignalR callback when entity is added to HA."""
        if self._signalr_manager and self._group_id:
            self._signalr_manager.register_callback(
                self._group_id, self._async_signalr_update
            )
            _LOGGER.debug("Registered SignalR callback for group %s", self._group_id)

    async def async_will_remove_from_hass(self) -> None:
        """Unregister SignalR callback when entity is removed."""
        if self._signalr_manager and self._group_id:
            self._signalr_manager.unregister_callback(self._group_id)

    async def _async_signalr_update(self) -> None:
        """Handle a real-time SignalR notification by refreshing state from API."""
        _LOGGER.debug("SignalR triggered update for group %s", self._group_id)
        await self.async_update()
        self.async_write_ha_state()

    def _update_from_data(self, data: dict) -> None:
        """Update internal state from group data."""
        if not data:
            return

        self._away_mode = data.get("awayMode", False)

        # Convert away setpoint temperature, rounded to nearest 0.5°C
        away_temp = data.get("awaySetPointTemp")
        if away_temp is not None:
            self._away_setpoint = round((away_temp / 100.0) * 2) / 2
        else:
            self._away_setpoint = None

    @property
    def hvac_mode(self) -> HVACMode:
        """Return current HVAC mode - groups are always in HEAT."""
        return HVACMode.HEAT

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode."""
        if self._away_mode:
            return "Away"
        return "Home"

    @property
    def current_temperature(self) -> float | None:
        """Groups don't report current temperature."""
        return None

    @property
    def target_temperature(self) -> float | None:
        """Return the away setpoint temperature."""
        return self._away_setpoint

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return additional state attributes."""
        attrs: dict[str, Any] = {}
        attrs["away_mode"] = "On" if self._away_mode else "Off"
        if self._away_setpoint is not None:
            attrs["away_setpoint"] = self._away_setpoint
        return attrs

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set preset mode - Home or Away."""
        if not self._group_id:
            return

        # "Away" preset enables away mode, "Home" disables it
        away_mode = preset_mode == "Away"

        success = await self._api.set_group_away_mode(self._group_id, away_mode)
        if success:
            self._away_mode = away_mode
            _LOGGER.debug("Group %s preset set to %s", self._attr_name, preset_mode)
            self.async_write_ha_state()
        else:
            _LOGGER.warning(
                "Failed to set preset mode for %s, reverting to actual state",
                self._attr_name,
            )
            await self.async_update()
            self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Groups don't support HVAC mode changes."""
        pass

    async def async_update(self) -> None:
        """Update group data."""
        if not self._group_id:
            return

        # Fetch all groups and find ours
        groups = await self._api.get_groups()
        for group in groups:
            if group.get("groupId") == self._group_id:
                self._update_from_data(group)
                self._attr_available = True
                return

        # Group not found
        self._attr_available = False
