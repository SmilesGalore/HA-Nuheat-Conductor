"""SignalR client for Nuheat Conductor change notifications.

Connects to the Nuheat v1 change notification hub and pushes real-time
updates to registered entity callbacks. Falls back gracefully to the
90-second polling interval if the connection cannot be established or drops.

Notification types (v1):
    1 = UserAccount
    2 = Thermostat  (serial number as id)
    3 = Schedule    (serial number as id)
    4 = Group       (group id as id)
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable
from typing import Any

from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.core import HomeAssistant

from .auth import is_token_rejected, start_reauth
from .const import API_URL

_LOGGER = logging.getLogger(__name__)

# Notification type constants (v1 hub)
NOTIFY_TYPE_THERMOSTAT = 2
NOTIFY_TYPE_GROUP = 4

# SignalR hub endpoint
SIGNALR_HUB_URL = f"{API_URL}/v1/changenotifications"

# Reconnection backoff delays in seconds
RECONNECT_DELAYS = [5, 10, 30, 60]

# How long to wait for the WebSocket handshake to complete
HANDSHAKE_TIMEOUT = 10

# SignalR protocol version
SIGNALR_PROTOCOL = {"protocol": "json", "version": 1}

# SignalR uses a record separator (0x1e) to delimit messages
RECORD_SEPARATOR = "\x1e"


class NuheatSignalRManager:
    """Manages a persistent SignalR WebSocket connection to Nuheat's notification hub.

    Entities register callbacks by serial number or group ID. When a notification
    arrives, the matching callback is invoked so the entity can refresh its state
    immediately rather than waiting for the next poll cycle.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        oauth_session: config_entry_oauth2_flow.OAuth2Session,
    ) -> None:
        """Initialise the SignalR manager."""
        self._hass = hass
        self._oauth_session = oauth_session
        self._websession = async_get_clientsession(hass)

        # Callbacks registered by entities: {id: callback}
        # id is either a thermostat serial number or a group ID string
        self._callbacks: dict[str, Callable[[], None]] = {}

        self._task: asyncio.Task | None = None
        self._running = False
        self._connected = False
        self._reconnect_attempt = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def is_connected(self) -> bool:
        """Return True if the SignalR connection is currently active."""
        return self._connected

    def register_callback(self, entity_id: str, callback: Callable[[], None]) -> None:
        """Register a callback for a thermostat serial number or group ID.

        The callback will be called (with no arguments) whenever a notification
        arrives for that entity_id.
        """
        self._callbacks[entity_id] = callback
        _LOGGER.debug("Registered SignalR callback for %s", entity_id)

    def unregister_callback(self, entity_id: str) -> None:
        """Remove a previously registered callback."""
        self._callbacks.pop(entity_id, None)
        _LOGGER.debug("Unregistered SignalR callback for %s", entity_id)

    async def async_start(self) -> None:
        """Start the SignalR connection loop as a background task."""
        if self._task and not self._task.done():
            _LOGGER.debug("SignalR manager already running")
            return
        self._running = True
        self._task = self._hass.async_create_background_task(
            self._connection_loop(),
            name="nuheat_conductor_signalr",
        )
        _LOGGER.debug("SignalR background task started")

    async def async_stop(self) -> None:
        """Stop the SignalR connection loop cleanly."""
        self._running = False
        self._connected = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        _LOGGER.debug("SignalR manager stopped")

    # ------------------------------------------------------------------
    # Connection loop
    # ------------------------------------------------------------------

    async def _connection_loop(self) -> None:
        """Main loop: connect, listen, reconnect on failure."""
        while self._running:
            try:
                await self._connect_and_listen()
                # Clean exit - reset the reconnect counter
                self._reconnect_attempt = 0
            except asyncio.CancelledError:
                _LOGGER.debug("SignalR connection loop cancelled")
                break
            except Exception as err:
                if is_token_rejected(err):
                    # Retrying with a dead refresh token can never succeed.
                    # Prompt the user to sign in again and stop; the entry is
                    # reloaded (and this manager restarted) once they do.
                    _LOGGER.error(
                        "Nuheat rejected the saved login (%s); "
                        "re-authentication required",
                        err,
                    )
                    start_reauth(self._oauth_session)
                    self._running = False
                    self._connected = False
                    break
                _LOGGER.exception("SignalR connection error")

            if not self._running:
                break

            # Exponential backoff reconnect
            delay = RECONNECT_DELAYS[
                min(self._reconnect_attempt, len(RECONNECT_DELAYS) - 1)
            ]
            self._reconnect_attempt += 1
            self._connected = False
            _LOGGER.warning(
                "SignalR disconnected. Reconnecting in %ds (attempt %d)",
                delay,
                self._reconnect_attempt,
            )
            await asyncio.sleep(delay)

    # ------------------------------------------------------------------
    # Connection and message handling
    # ------------------------------------------------------------------

    async def _get_access_token(self) -> str:
        """Get a fresh access token from the OAuth session."""
        await self._oauth_session.async_ensure_token_valid()
        return self._oauth_session.token["access_token"]

    def _token_expires_in(self) -> float:
        """Return seconds until the current token expires, or 0 if unknown."""
        try:
            expires_at = self._oauth_session.token.get("expires_at", 0)
            import time

            remaining = expires_at - time.time()
            return max(remaining, 0)
        except Exception:
            return 0

    async def _connect_and_listen(self) -> None:
        """Establish a WebSocket connection, perform the SignalR handshake,
        subscribe to notifications, and listen for messages.
        """
        token = await self._get_access_token()
        url = f"{SIGNALR_HUB_URL}?token={token}"

        _LOGGER.debug("Connecting to SignalR hub at %s", SIGNALR_HUB_URL)

        async with self._websession.ws_connect(
            url,
            headers={"Authorization": f"Bearer {token}"},
            heartbeat=20,  # Send ping every 20s, aiohttp waits 15s for PONG
            timeout=HANDSHAKE_TIMEOUT,
        ) as ws:
            _LOGGER.debug("WebSocket connection established, sending handshake")

            # Step 1: Send the SignalR JSON protocol handshake
            handshake_msg = json.dumps(SIGNALR_PROTOCOL) + RECORD_SEPARATOR
            _LOGGER.debug("Sending handshake: %s", handshake_msg)
            await ws.send_str(handshake_msg)

            # Step 2: Wait for the handshake response
            _LOGGER.debug("Waiting for handshake response...")
            handshake_response = await asyncio.wait_for(
                ws.receive(), timeout=HANDSHAKE_TIMEOUT
            )
            _LOGGER.debug(
                "Handshake response received: type=%s, data=%s",
                handshake_response.type,
                handshake_response.data,
            )

            # Handle both text and binary responses
            response_text = None
            if hasattr(handshake_response, "data"):
                if handshake_response.type == 2 and isinstance(
                    handshake_response.data, bytes
                ):  # BINARY
                    response_text = handshake_response.data.decode("utf-8").rstrip(
                        RECORD_SEPARATOR
                    )
                elif handshake_response.type == 1 or isinstance(
                    handshake_response.data, str
                ):  # TEXT
                    response_text = handshake_response.data.rstrip(RECORD_SEPARATOR)

            if response_text is not None:
                _LOGGER.debug("SignalR handshake response: %s", response_text)
                response_data = json.loads(response_text) if response_text else {}
                if "error" in response_data:
                    raise ConnectionError(
                        f"SignalR handshake failed: {response_data['error']}"
                    )
            else:
                _LOGGER.warning(
                    "Unexpected handshake response type: %s - continuing anyway",
                    handshake_response.type,
                )

            # Step 3: Subscribe to thermostat and group notifications
            _LOGGER.debug("Sending subscription request")
            await self._subscribe(ws)

            self._connected = True
            self._reconnect_attempt = 0  # Reset as soon as connection succeeds
            _LOGGER.info("SignalR connected to Nuheat notification hub")

            # Step 4: Listen for incoming messages
            # aiohttp WSMsgType values: TEXT=1, BINARY=2, PING=9, PONG=10, CLOSE=8, ERROR=258
            async for msg in ws:
                if not self._running:
                    break

                # Proactively reconnect 5 minutes before the token expires
                # so the new connection uses a fresh token
                if self._token_expires_in() < 300:
                    _LOGGER.debug(
                        "SignalR token expiring soon, reconnecting with fresh token"
                    )
                    break

                _LOGGER.debug(
                    "SignalR raw message: type=%s, data=%s", msg.type, msg.data
                )
                if msg.type == 1:  # WSMsgType.TEXT
                    await self._handle_message(msg.data)
                elif msg.type == 2:  # WSMsgType.BINARY
                    try:
                        await self._handle_message(msg.data.decode("utf-8"))
                    except Exception:
                        _LOGGER.debug("Could not decode binary SignalR message")
                elif msg.type == 258:  # WSMsgType.ERROR
                    _LOGGER.error("SignalR WebSocket error: %s", msg.data)
                    break
                elif msg.type in (8, 9, 10):  # CLOSE, PING, PONG
                    _LOGGER.debug("SignalR WebSocket closing (type=%s)", msg.type)
                    break

        self._connected = False

    async def _subscribe(self, ws: Any) -> None:
        """Send a SignalR invocation to subscribe to notifications.

        Uses invoke() semantics (with invocationId) matching the JS SDK's
        connection.invoke("Subscribe", notificationTypes) as per Nuheat docs.
        Types: 1=UserAccount, 2=Thermostat, 3=Schedule, 4=Group
        """
        # Integer type IDs as expected by the server's C# method signature
        # (strings caused "Error binding arguments" - server expects int[], not string[])
        notification_types = [1, 2, 3, 4]
        invocation = {
            "type": 1,
            "invocationId": "subscribe_1",
            "target": "Subscribe",
            "arguments": [notification_types],
        }
        msg = json.dumps(invocation) + RECORD_SEPARATOR
        _LOGGER.debug("Sending subscription invocation: %s", msg)
        await ws.send_str(msg)

    # ------------------------------------------------------------------
    # Message handling
    # ------------------------------------------------------------------

    async def _handle_message(self, raw: str) -> None:
        """Parse an incoming SignalR message and dispatch to callbacks."""
        # Messages may be batched and separated by the record separator
        for chunk in raw.split(RECORD_SEPARATOR):
            chunk = chunk.strip()
            if not chunk:
                continue
            try:
                message = json.loads(chunk)
            except json.JSONDecodeError:
                _LOGGER.debug("Could not parse SignalR message: %s", chunk)
                continue

            await self._dispatch_message(message)

    async def _dispatch_message(self, message: dict) -> None:
        """Dispatch a parsed SignalR message to the appropriate entity callback."""
        msg_type = message.get("type")

        # Type 1 = Invocation (server calling client method "Notify")
        if msg_type == 1:
            target = message.get("target", "")
            if target == "Notify":
                arguments = message.get("arguments", [])
                # Nuheat sends arguments as a list containing either:
                # - A single notification dict: [{"type":2,"id":"..."}]
                # - A list of notification dicts: [[{"type":2,...},{"type":4,...}]]
                # Handle both formats
                for arg in arguments:
                    if isinstance(arg, dict):
                        # Single notification object directly in arguments list
                        await self._handle_notification(arg)
                    elif isinstance(arg, list):
                        # List of notification objects
                        for notification in arg:
                            if isinstance(notification, dict):
                                await self._handle_notification(notification)

        # Type 6 = Ping (keep-alive from server, no action needed)
        elif msg_type == 6:
            _LOGGER.debug("SignalR ping received")

        # Type 3 = Completion (response to our Subscribe invocation)
        elif msg_type == 3:
            _LOGGER.debug("SignalR subscription confirmed by server: %s", message)

        else:
            _LOGGER.debug("Unhandled SignalR message type %s: %s", msg_type, message)

    async def _handle_notification(self, notification: dict) -> None:
        """Handle a single notification and fire the matching entity callback."""
        notify_type = notification.get("type")
        entity_id = str(notification.get("id", ""))
        timestamp = notification.get("timeStamp", "")

        _LOGGER.debug(
            "SignalR notification: type=%s, id=%s, timestamp=%s",
            notify_type,
            entity_id,
            timestamp,
        )

        if notify_type not in (NOTIFY_TYPE_THERMOSTAT, NOTIFY_TYPE_GROUP):
            _LOGGER.debug("Ignoring notification type %s", notify_type)
            return

        callback = self._callbacks.get(entity_id)
        if callback:
            _LOGGER.debug("Dispatching SignalR update for %s", entity_id)
            # Schedule the callback on the event loop without blocking the listener
            self._hass.async_create_task(self._invoke_callback(callback, entity_id))
        else:
            _LOGGER.debug(
                "No callback registered for id %s (type %s)", entity_id, notify_type
            )

    async def _invoke_callback(
        self, callback: Callable[[], None], entity_id: str
    ) -> None:
        """Invoke a registered entity callback safely."""
        try:
            await callback()
        except Exception:
            _LOGGER.exception("Error invoking SignalR callback for %s", entity_id)
