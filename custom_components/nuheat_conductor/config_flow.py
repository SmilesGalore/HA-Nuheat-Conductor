"""Config flow for Nuheat Conductor using OAuth2 Authorization Code flow."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigFlowResult
from homeassistant.helpers import config_entry_oauth2_flow

from .const import (
    AUTHORIZE_URL,
    CLIENT_ID,
    CLIENT_SECRET,
    DOMAIN,
    OAUTH2_SCOPES,
    TOKEN_URL,
)

_LOGGER = logging.getLogger(__name__)


class NuheatConductorLocalOAuth2Implementation(
    config_entry_oauth2_flow.LocalOAuth2Implementation
):
    """Local OAuth2 implementation for Nuheat Conductor with embedded credentials."""

    def __init__(self, hass) -> None:
        """Initialize the OAuth2 implementation."""
        super().__init__(
            hass,
            DOMAIN,
            CLIENT_ID,
            CLIENT_SECRET,
            AUTHORIZE_URL,
            TOKEN_URL,
        )

    @property
    def extra_authorize_data(self) -> dict[str, Any]:
        """Extra data to include in the authorize URL."""
        return {"scope": " ".join(OAUTH2_SCOPES)}


class NuheatConductorOAuth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler,
    domain=DOMAIN,
):
    """Handle a config flow for Nuheat Conductor."""

    DOMAIN = DOMAIN
    VERSION = 1

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return _LOGGER

    @property
    def extra_authorize_data(self) -> dict[str, Any]:
        """Extra data that needs to be appended to the authorize url."""
        return {"scope": " ".join(OAUTH2_SCOPES)}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        await self.async_set_unique_id(DOMAIN)

        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        # Check if there's an in-progress flow (happens when OAuth was interrupted)
        if self.hass.config_entries.flow.async_progress_by_handler(DOMAIN):
            _LOGGER.warning(
                "Detected interrupted OAuth flow. User should restart Home Assistant before retrying."
            )

        # Register our implementation
        self.async_register_implementation(
            self.hass,
            NuheatConductorLocalOAuth2Implementation(self.hass),
        )

        return await super().async_step_user(user_input)

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        # Register our implementation for reauth
        self.async_register_implementation(
            self.hass,
            NuheatConductorLocalOAuth2Implementation(self.hass),
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauth dialog."""
        if user_input is None:
            return self.async_show_form(step_id="reauth_confirm")
        return await self.async_step_user()

    async def async_oauth_create_entry(self, data: dict[str, Any]) -> ConfigFlowResult:
        """Create an entry for the flow."""
        try:
            existing_entry = await self.async_set_unique_id(DOMAIN)
            if existing_entry:
                self.hass.config_entries.async_update_entry(existing_entry, data=data)
                await self.hass.config_entries.async_reload(existing_entry.entry_id)
                return self.async_abort(reason="reauth_successful")

            return self.async_create_entry(title="Nuheat Conductor", data=data)
        except Exception as err:
            _LOGGER.error("Failed to create entry after OAuth: %s", err)
            return self.async_abort(reason="oauth_error")
