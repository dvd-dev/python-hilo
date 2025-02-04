"""Define a connection to the Hilo websocket."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import IntEnum
import json
from os import environ
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional, Tuple
from urllib import parse

from aiohttp import ClientSession, ClientWebSocketResponse, WSMsgType
from aiohttp.client_exceptions import (
    ClientError,
    ServerDisconnectedError,
    WSServerHandshakeError,
)
from yarl import URL

from pyhilo.const import (
    AUTOMATION_CHALLENGE_ENDPOINT,
    AUTOMATION_DEVICEHUB_ENDPOINT,
    DEFAULT_USER_AGENT,
    LOG,
)
from pyhilo.exceptions import (
    CannotConnectError,
    ConnectionClosedError,
    ConnectionFailedError,
    InvalidCredentialsError,
    InvalidMessageError,
    NotConnectedError,
)
from pyhilo.util import schedule_callback

if TYPE_CHECKING:
    from pyhilo import API

DEFAULT_WATCHDOG_TIMEOUT = timedelta(minutes=5)


class SignalRMsgType(IntEnum):
    INVOKE = 0x1
    STREAM = 0x2
    COMPLETE = 0x3
    STREAM_INVOCATION = 0x4
    CANCEL_INVOCATION = 0x5
    PING = 0x6
    CLOSE = 0x7
    UNKNOWN = 0xFF

    @classmethod
    def has_value(cls, value: int) -> bool:
        return value in cls._value2member_map_

    @classmethod
    def value(cls, value: int) -> IntEnum:  # type: ignore
        return cls._value2member_map_.get(value, cls.UNKNOWN)  # type: ignore


@dataclass(frozen=True)
class WebsocketEvent:
    """Define a representation of a message."""

    event_type_id: int
    target: str
    arguments: list[list]
    invocation: int | None
    error: str | None
    timestamp: datetime = field(default=datetime.now())
    event_type: str | None = field(init=False)

    def __post_init__(self) -> None:
        if SignalRMsgType.has_value(self.event_type_id):
            object.__setattr__(
                self, "event_type", SignalRMsgType.value(self.event_type_id).name
            )
        if self.event_type_id == SignalRMsgType.CLOSE:
            LOG.error(
                f"Received close event from SignalR: Error: {self.event_type} Target: {self.target} Args: {self.arguments} Error: {self.error}"
            )


def websocket_event_from_payload(payload: dict[str, Any]) -> WebsocketEvent:
    """Create a Message object from a websocket event payload."""
    return WebsocketEvent(
        payload["type"],
        payload.get("target", ""),
        payload.get("arguments", ""),
        payload.get("invocationId"),
        payload.get("error"),
    )


class Watchdog:
    """Define a watchdog to kick the websocket connection at intervals."""

    def __init__(
        self, action: Callable[..., Any], timeout: timedelta = DEFAULT_WATCHDOG_TIMEOUT
    ):
        """Initialize."""
        self._action = action
        self._action_task: asyncio.Task | None = None
        self._loop = asyncio.get_running_loop()
        self._timeout_seconds = timeout.total_seconds()
        self._timer_task: asyncio.TimerHandle | None = None

    def _on_expire(self) -> None:
        """Log and act when the watchdog expires."""
        LOG.warning("Websocket: Watchdog expired")
        schedule_callback(self._action)

    def cancel(self) -> None:
        """Cancel the watchdog."""
        if self._timer_task:
            self._timer_task.cancel()
            self._timer_task = None

    def trigger(self) -> None:
        """Trigger the watchdog."""
        if self._timer_task:
            self._timer_task.cancel()

        self._timer_task = self._loop.call_later(self._timeout_seconds, self._on_expire)


class WebsocketClient:
    """A websocket connection to the Hilo cloud.
    Note that this class shouldn't be instantiated directly; it will be instantiated as
    :param api: A :meth:`pyhilo.API` object
    :type api: :meth:`pyhilo.API`
    """

    def __init__(self, api: API) -> None:
        """Initialize."""
        self._api = api
        self._connect_callbacks: list[Callable[..., None]] = []
        self._disconnect_callbacks: list[Callable[..., None]] = []
        self._event_callbacks: list[Callable[..., None]] = []
        self._loop = asyncio.get_running_loop()
        self._watchdog = Watchdog(self.async_reconnect)
        self._ready_event: asyncio.Event = asyncio.Event()
        self._ready: bool = False
        self._queued_tasks: list[asyncio.TimerHandle] = []

        # These will get filled in after initial authentication:
        self._client: ClientWebSocketResponse | None = None

    @property
    def connected(self) -> bool:
        """Return if currently connected to the websocket."""
        return self._client is not None and not self._client.closed

    @staticmethod
    def _add_callback(
        callback_list: list, callback: Callable[..., Any]
    ) -> Callable[..., None]:
        """Add a callback callback to a particular list."""
        callback_list.append(callback)

        def remove() -> None:
            """Remove the callback."""
            callback_list.remove(callback)

        return remove

    async def _async_receive_json(self) -> list[Dict[str, Any]]:
        """Receive a JSON response from the websocket server."""
        assert self._client

        response = await self._client.receive(300)

        if response.type in (WSMsgType.CLOSE, WSMsgType.CLOSED, WSMsgType.CLOSING):
            LOG.error(f"Websocket: Received event to close connection: {response.type}")
            raise ConnectionClosedError("Connection was closed.")

        if response.type == WSMsgType.ERROR:
            LOG.error(
                f"Websocket: Received error event, Connection failed: {response.type}"
            )
            raise ConnectionFailedError

        if response.type != WSMsgType.TEXT:
            LOG.error(f"Websocket: Received invalid message: {response}")
            raise InvalidMessageError(f"Received non-text message: {response.type}")

        messages: list[Dict[str, Any]] = []
        try:
            # Sometimes the http lib stacks multiple messages in the buffer, we need to split them to process.
            received_messages = response.data.strip().split("\x1e")
            for msg in received_messages:
                data = json.loads(msg)
                messages.append(data)
        except ValueError as v_exc:
            raise InvalidMessageError("Received invalid JSON") from v_exc
        except json.decoder.JSONDecodeError as j_exc:
            LOG.error(f"Received invalid JSON: {msg}")
            LOG.exception(j_exc)
            data = {}

        self._watchdog.trigger()

        return messages

    async def _async_send_json(self, payload: dict[str, Any]) -> None:
        """Send a JSON message to the websocket server.
        Raises NotConnectedError if client is not connected.
        """
        if not self.connected:
            raise NotConnectedError

        assert self._client

        if self._api.log_traces:
            LOG.debug(
                f"[TRACE] Sending data to websocket {self._api.endpoint} : {json.dumps(payload)}"
            )
        # Hilo added a control character (chr(30)) at the end of each payload they send.
        # They also expect this char to be there at the end of every payload we send them.
        await self._client.send_str(json.dumps(payload) + chr(30))

    def _parse_message(self, msg: dict[str, Any]) -> None:
        """Parse an incoming message."""
        if self._api.log_traces:
            LOG.debug(f"[TRACE] Received message from websocket: {msg}")
        if msg.get("type") == SignalRMsgType.PING:
            schedule_callback(self._async_pong)
            return
        if isinstance(msg, dict) and not len(msg):
            self._ready = True
            self._ready_event.set()
            LOG.info("Websocket: Ready for data")
            return
        event = websocket_event_from_payload(msg)
        for callback in self._event_callbacks:
            schedule_callback(callback, event)

    def add_connect_callback(self, callback: Callable[..., Any]) -> Callable[..., None]:
        """Add a callback callback to be called after connecting.
        :param callback: The method to call after connecting
        :type callback: ``Callable[..., None]``
        """
        return self._add_callback(self._connect_callbacks, callback)

    def add_disconnect_callback(
        self, callback: Callable[..., Any]
    ) -> Callable[..., None]:
        """Add a callback callback to be called after disconnecting.
        :param callback: The method to call after disconnecting
        :type callback: ``Callable[..., None]``
        """
        return self._add_callback(self._disconnect_callbacks, callback)

    def add_event_callback(self, callback: Callable[..., Any]) -> Callable[..., None]:
        """Add a callback callback to be called upon receiving an event.
        Note that callbacks should expect to receive a WebsocketEvent object as a
        parameter.
        :param callback: The method to call after receiving an event.
        :type callback: ``Callable[..., None]``
        """
        return self._add_callback(self._event_callbacks, callback)

    async def async_connect(self) -> None:
        """Connect to the websocket server."""
        if self.connected:
            LOG.debug("Websocket: async_connect() called but already connected")
            return

        LOG.info("Websocket: Connecting to server")
        if self._api.log_traces:
            LOG.debug(f"[TRACE] Websocket URL: {self._api.full_url}")
        headers = {
            "Sec-WebSocket-Extensions": "permessage-deflate; client_max_window_bits",
            "Pragma": "no-cache",
            "Cache-Control": "no-cache",
            "User-Agent": DEFAULT_USER_AGENT,
            "Origin": "http://localhost",
            "Accept-Language": "en-US,en;q=0.9",
        }
        # NOTE(dvd): for troubleshooting purpose we can pass a mitmproxy as env variable
        proxy_env: dict[str, Any] = {}
        if proxy := environ.get("WS_PROXY"):
            proxy_env["proxy"] = proxy
            proxy_env["verify_ssl"] = False

        try:
            self._client = await self._api.session.ws_connect(
                URL(
                    self._api.full_url,
                    encoded=True,
                ),
                heartbeat=55,
                headers=headers,
                **proxy_env,
            )
        except (ClientError, ServerDisconnectedError, WSServerHandshakeError) as err:
            LOG.error(f"Unable to connect to WS server {err}")
            if hasattr(err, "status") and err.status in (401, 403, 404, 409):
                raise InvalidCredentialsError("Invalid credentials") from err
        except Exception as err:
            LOG.error(f"Unable to connect to WS server {err}")
            raise CannotConnectError(err) from err

        LOG.info("Connected to websocket server")
        self._watchdog.trigger()
        for callback in self._connect_callbacks:
            schedule_callback(callback)

    async def _clean_queue(self) -> None:
        for task in self._queued_tasks:
            task.cancel()

    async def async_disconnect(self) -> None:
        """Disconnect from the websocket server."""
        await self._clean_queue()
        if not self.connected:
            return

        assert self._client

        await self._client.close()

        LOG.info("Disconnected from websocket server")

    async def async_listen(self) -> None:
        """Start listening to the websocket server."""
        assert self._client
        LOG.info("Websocket: Listen started.")
        try:
            while not self._client.closed:
                messages = await self._async_receive_json()
                for msg in messages:
                    self._parse_message(msg)
        except ConnectionClosedError as err:
            LOG.error(f"Websocket: Closed while listening: {err}")
            LOG.exception(err)
            pass
        except InvalidMessageError as err:
            LOG.warning(f"Websocket: Received invalid json : {err}")
            pass
        finally:
            LOG.info("Websocket: Listen completed; cleaning up")
            self._watchdog.cancel()
            await self._clean_queue()

            for callback in self._disconnect_callbacks:
                schedule_callback(callback)

    async def async_reconnect(self) -> None:
        """Reconnect (and re-listen, if appropriate) to the websocket."""
        LOG.warning("Websocket: Reconnecting")
        await self.async_disconnect()
        await asyncio.sleep(5)
        await self.async_connect()

    async def send_status(self) -> None:
        LOG.debug("Sending status")
        self._ready = False
        await self._async_send_json({"protocol": "json", "version": 1})

    async def _async_pong(self) -> None:
        await self._async_send_json({"type": SignalRMsgType.PING})

    async def async_invoke(
        self, arg: list, target: str, inv_id: int, inv_type: WSMsgType = WSMsgType.TEXT
    ) -> None:
        if not self._ready:
            LOG.warning(
                f"Delaying invoke {target} {inv_id} {arg}: Websocket not ready."
            )
            try:
                await asyncio.wait_for(self._ready_event.wait(), timeout=10)
            except asyncio.TimeoutError:
                return
            self._ready_event.clear()
        await self._async_send_json(
            {
                "arguments": arg,
                "invocationId": str(inv_id),
                "target": target,
                "type": inv_type,
            }
        )


@dataclass
class WebsocketConfig:
    """Configuration for a websocket connection"""

    endpoint: str
    url: Optional[str] = None
    token: Optional[str] = None
    connection_id: Optional[str] = None
    full_url: Optional[str] = None
    log_traces: bool = True
    session: ClientSession | None = None


class WebsocketManager:
    """Manages multiple websocket connections for the Hilo API"""

    def __init__(
        self, session: ClientSession, async_request, state_yaml: str, set_state_callback
    ) -> None:
        """Initialize the websocket manager.

        Args:
            session: The aiohttp client session
            async_request: The async request method from the API class
            state_yaml: Path to the state file
            set_state_callback: Callback to save state
        """
        self.session = session
        self.async_request = async_request
        self._state_yaml = state_yaml
        self._set_state = set_state_callback
        self._shared_token = None  # ic-dev21 need to share the token

        # Initialize websocket configurations
        self.devicehub = WebsocketConfig(endpoint=AUTOMATION_DEVICEHUB_ENDPOINT, session=session)
        self.challengehub = WebsocketConfig(endpoint=AUTOMATION_CHALLENGE_ENDPOINT, session=session)

    async def initialize_websockets(self) -> None:
        """Initialize both websocket connections"""
        # ic-dev21 get token from device hub
        await self.refresh_token(self.devicehub, get_new_token=True)
        # ic-dev21 reuse it for challenge hub
        await self.refresh_token(self.challengehub, get_new_token=True)

    async def refresh_token(
        self, config: WebsocketConfig, get_new_token: bool = True
    ) -> None:
        """Refresh token for a specific websocket configuration.

        Args:
            config: The websocket configuration to refresh
        """
        if get_new_token:
            config.url, self._shared_token = await self._negotiate(config)
            config.token = self._shared_token
        else:
            # ic-dev21 reuse existing token but get new URL
            config.url, _ = await self._negotiate(config)
            config.token = self._shared_token

        await self._get_websocket_params(config)

    async def _negotiate(self, config: WebsocketConfig) -> Tuple[str, str]:
        """Negotiate websocket connection and get URL and token.

        Args:
            config: The websocket configuration to negotiate

        Returns:
            Tuple containing the websocket URL and access token
        """
        LOG.debug(f"Getting websocket url for {config.endpoint}")
        url = f"{config.endpoint}/negotiate"
        LOG.debug(f"Negotiate URL is {url}")

        resp = await self.async_request("post", url)
        ws_url = resp.get("url")
        ws_token =   resp.get("accessToken")
          

        # Save state
        state_key = (
            "websocket"
            if config.endpoint == "AUTOMATION_DEVICEHUB_ENDPOINT"
            else "websocket2"
        )
        await self._set_state(
            self._state_yaml,
            state_key,
            {
                "url": ws_url,
                "token": ws_token,
            },
        )

        return ws_url, ws_token

    async def _get_websocket_params(self, config: WebsocketConfig) -> None:
        """Get websocket parameters including connection ID.

        Args:
            config: The websocket configuration to get parameters for
        """
        uri = parse.urlparse(config.url)
        LOG.debug(f"Getting websocket params for {config.endpoint}")
        LOG.debug(f"Getting uri {uri}")

        resp = await self.async_request(
            "post",
            f"{uri.path}negotiate?{uri.query}",
            host=uri.netloc,
            headers={
                "authorization": f"Bearer {config.token}",
            },
        )

        config.connection_id = resp.get("connectionId", "")
        config.full_url = (
            f"{config.url}&id={config.connection_id}&access_token={config.token}"
        )
        LOG.debug(f"Getting full ws URL {config.full_url}")

        transport_dict = resp.get("availableTransports", [])
        websocket_dict = {
            "connection_id": config.connection_id,
            "available_transports": transport_dict,
            "full_url": config.full_url,
        }

        # Save state
        state_key = (
            "websocket"
            if config.endpoint == "AUTOMATION_DEVICEHUB_ENDPOINT"
            else "websocket2"
        )
        LOG.debug(f"Calling set_state {state_key}_params")
        await self._set_state(self._state_yaml, state_key, websocket_dict)
