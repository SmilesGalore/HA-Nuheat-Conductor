"""Helpers for handling expired or revoked Nuheat OAuth sessions."""

from __future__ import annotations

from aiohttp import ClientResponseError

from homeassistant.helpers import config_entry_oauth2_flow

# The Nuheat identity server answers 400 (invalid_grant) when the refresh token
# has expired or been revoked, and 401/403 when the session is no longer valid.
# Anything else (5xx, timeouts, DNS failures) is treated as temporary.
_TOKEN_REJECTED_STATUSES = frozenset({400, 401, 403})


def is_token_rejected(err: BaseException) -> bool:
    """Return True if NuHeat rejected our credentials (user must sign in again)."""
    return (
        isinstance(err, ClientResponseError) and err.status in _TOKEN_REJECTED_STATUSES
    )


def start_reauth(oauth_session: config_entry_oauth2_flow.OAuth2Session) -> None:
    """Ask the user to re-authenticate. Safe to call repeatedly (no duplicate flows)."""
    oauth_session.config_entry.async_start_reauth(oauth_session.hass)
