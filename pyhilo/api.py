from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import json
import random
import string
import sys
from typing import Any, Callable, Union, cast
from urllib import parse

from aiohttp import ClientSession
from aiohttp.client_exceptions import ClientResponseError
import backoff
from homeassistant.helpers import config_entry_oauth2_flow

from pyhilo.const import (
    ANDROID_CLIENT_ENDPOINT,
    ANDROID_CLIENT_HEADERS,
    ANDROID_CLIENT_HOSTNAME,
    ANDROID_CLIENT_POST,
    API_AUTOMATION_ENDPOINT,
    API_CHALLENGE_ENDPOINT,
    API_EVENTS_ENDPOINT,
    API_GD_SERVICE_ENDPOINT,
    API_HOSTNAME,
    API_NOTIFICATIONS_ENDPOINT,
    API_REGISTRATION_ENDPOINT,
    API_REGISTRATION_HEADERS,
    AUTOMATION_CHALLENGE_ENDPOINT,
    AUTOMATION_DEVICEHUB_ENDPOINT,
    DEFAULT_STATE_FILE,
    DEFAULT_USER_AGENT,
    FB_APP_ID,
    FB_AUTH_VERSION,
    FB_ID_LEN,
    FB_INSTALL_ENDPOINT,
    FB_INSTALL_HEADERS,
    FB_INSTALL_HOSTNAME,
    FB_SDK_VERSION,
    HILO_READING_TYPES,
    LOG,
    REQUEST_RETRY,
    SUBSCRIPTION_KEY,
)
from pyhilo.device import DeviceAttribute, HiloDevice, get_device_attributes
from pyhilo.exceptions import InvalidCredentialsError, RequestError
from pyhilo.util.state import (
    StateDict,
    WebsocketDict,
    WebsocketTransportsDict,
    get_state,
    set_state,
)
from pyhilo.websocket import WebsocketClient, WebsocketConfig, WebsocketManager


class API:
    """An API object to interact with the Hilo cloud.

    :param session: The ``aiohttp`` ``ClientSession`` session used for all HTTP requests
    :type session: ``aiohttp.client.ClientSession``
    :param request_retries: The default number of request retries to use, defaults to REQUEST_RETRY
    :type request_retries: ``int``, optional
    """

    def __init__(
        self,
        *,
        session: ClientSession,
        oauth_session: config_entry_oauth2_flow.OAuth2Session,
        request_retries: int = REQUEST_RETRY,
        log_traces: bool = False,
    ) -> None:
        """Initialize"""
        self._backoff_refresh_lock_api = asyncio.Lock()
        self._backoff_refresh_lock_ws = asyncio.Lock()
        self._request_retries = request_retries
        self._state_yaml: str = DEFAULT_STATE_FILE
        self.state: StateDict = {}
        self.async_request = self._wrap_request_method(self._request_retries)
        self.device_attributes = get_device_attributes()
        self.session: ClientSession = session
        self._oauth_session = oauth_session
        self.websocket: WebsocketClient
        self.log_traces = log_traces
        self._get_device_callbacks: list[Callable[..., Any]] = []

    @classmethod
    async def async_create(
        cls,
        *,
        session: ClientSession,
        oauth_session: config_entry_oauth2_flow.OAuth2Session,
        request_retries: int = REQUEST_RETRY,
        log_traces: bool = False,
    ) -> API:
        """Get an authenticated API object.
        :param session: The ``aiohttp`` ``ClientSession`` session used for all HTTP requests
        :type session: ``aiohttp.client.ClientSession``
        :param oauth_session: The session to make requests authenticated with OAuth2.
        :type oauth_session: ``config_entry_oauth2_flow.OAuth2Session``
        :param request_retries: The default number of request retries to use
        :type request_retries: ``int``
        :rtype: :meth:`pyhilo.api.API`
        """
        api = cls(
            session=session,
            oauth_session=oauth_session,
            request_retries=request_retries,
            log_traces=log_traces,
        )
        # Test token before post init
        await api.async_get_access_token()
        await api._async_post_init()
        return api

    @property
    def headers(self) -> dict[str, Any]:
        headers = {
            "User-Agent": DEFAULT_USER_AGENT,
        }
        return {
            **headers,
            **{
                "Content-Type": "application/json; charset=utf-8",
                "Ocp-Apim-Subscription-Key": SUBSCRIPTION_KEY,
            },
        }

    async def async_get_access_token(self) -> str:
        """Return a valid access token."""
        if not self._oauth_session.valid_token:
            await self._oauth_session.async_ensure_token_valid()

        return str(self._oauth_session.token["access_token"])

    def dev_atts(
        self, attribute: str, value_type: Union[str, None] = None
    ) -> Union[DeviceAttribute, str]:
        """Returns the DeviceAttribute object by attribute, camel case or not.

        :return: An object representing a device attribute.
        :rtype: ``pyhilo.device.DeviceAttribute``
        """
        return next(
            (
                x
                for x in self.device_attributes
                if x.hilo_attribute == attribute or x.attr == attribute
            ),
            DeviceAttribute(attribute, HILO_READING_TYPES.get(value_type, "null"))
            if value_type
            else attribute,
        )

    async def _get_fid_state(self) -> bool:
        """Looks up the cached state to define the firebase attributes
        on the API instances.

        :return: Whether or not we have cached firebase state
        :rtype: bool
        """
        self.state = await get_state(self._state_yaml)
        fb_state = self.state.get("firebase", {})
        if fb_fid := fb_state.get("fid"):
            self._fb_fid = fb_fid
            self._fb_name = fb_state.get("name", None)
            fb_token = fb_state.get("token", {})
            self._fb_refresh_token = fb_token.get("refresh")
            self._fb_auth_token = fb_token.get("access")
            self._fb_expires_at = fb_token.get("expires_at")
            return True
        return False

    async def _get_android_state(self) -> bool:
        """Looks up the cached state to define the android device token
        on the API instances.

        :return: Whether or not we have cached android state
        :rtype: bool
        """
        self.state = await get_state(self._state_yaml)
        android_state = self.state.get("android", {})
        if token := android_state.get("token"):
            self._device_token = token
            return True
        return False

    async def _get_device_token(self) -> None:
        """Retrieves the android token if it's not cached."""
        if not await self._get_android_state():
            await self.android_register()

    async def _get_fid(self) -> None:
        """Retrieves the firebase state if it's not cached."""
        if not await self._get_fid_state():
            self._fb_id = "".join(
                random.SystemRandom().choice(string.ascii_letters + string.digits)
                for _ in range(FB_ID_LEN)
            )
            await self.fb_install(self._fb_id)
            await self._get_fid_state()

    async def _async_request(
        self, method: str, endpoint: str, host: str = API_HOSTNAME, **kwargs: Any
    ) -> dict[str, Any]:
        """Execute an API request

        :param method: get/put/delete/etc
        :type method: str
        :param endpoint: Path to the endpoint
        :type endpoint: str
        :param host: Hostname to hit defaults to API_HOSTNAME
        :type host: str, optional
        :return: Generates a dict from the json content, or creates a new one based on status.
        :rtype: dict[str, Any]
        """
        kwargs.setdefault("headers", self.headers)
        access_token = await self.async_get_access_token()

        if endpoint.startswith(API_REGISTRATION_ENDPOINT):
            kwargs["headers"] = {**kwargs["headers"], **API_REGISTRATION_HEADERS}
        if endpoint.startswith(FB_INSTALL_ENDPOINT):
            kwargs["headers"] = {**kwargs["headers"], **FB_INSTALL_HEADERS}
        if endpoint.startswith(ANDROID_CLIENT_ENDPOINT):
            kwargs["headers"] = {**kwargs["headers"], **ANDROID_CLIENT_HEADERS}
        if host == API_HOSTNAME:
            kwargs["headers"]["authorization"] = f"Bearer {access_token}"
        kwargs["headers"]["Host"] = host

        # ic-dev21 trying Leicas suggestion
        if endpoint.startswith(AUTOMATION_CHALLENGE_ENDPOINT):
            # remove Ocp-Apim-Subscription-Key header to avoid 401 error
            kwargs["headers"].pop("Ocp-Apim-Subscription-Key", None)
            kwargs["headers"]["authorization"] = f"Bearer {access_token}"

        data: dict[str, Any] = {}
        url = parse.urljoin(f"https://{host}", endpoint)
        if self.log_traces:
            LOG.debug(f"[TRACE] Headers: {kwargs['headers']}")
            LOG.debug(f"[TRACE] Async request: {method} {url}")
        async with self.session.request(method, url, **kwargs) as resp:
            if "application/json" in resp.headers.get("content-type", ""):
                try:
                    data = await resp.json(content_type=None)
                except json.decoder.JSONDecodeError:
                    LOG.warning(f"JSON Decode error: {resp.__dict__}")
                    message = await resp.text()
                    data = {"error": message}
            else:
                data = {"message": await resp.text()}
            if self.log_traces:
                LOG.debug("[TRACE] Data received from /%s: %s", endpoint, data)
            resp.raise_for_status()
        return data

    def _get_url(
        self,
        endpoint: Union[str, None],
        location_id: int,
        gd: bool = False,
        drms: bool = False,
        events: bool = False,
        challenge: bool = False,
    ) -> str:
        """Generate a path to the requested endpoint.

        :param endpoint: Path to the endpoint
        :type endpoint: str
        :param location_id: Hilo location id
        :type location_id: int
        :param gd: Whether or not we should use the GD Service endpoint, defaults to False
        :type gd: bool, optional
        :param drms: Whether or not we should prepend the path with DRMS path, defaults to False
        :type drms: bool, optional
        :param challenge: Whether or not we should prepend the path with challenge path, defaults to False
        :type challenge: bool, optional
        :return: Path to the requested endpoint
        :rtype: str
        """
        base = API_AUTOMATION_ENDPOINT
        if gd:
            base = API_GD_SERVICE_ENDPOINT
        if drms:
            base += "/DRMS"
        if events:
            base = API_EVENTS_ENDPOINT + API_NOTIFICATIONS_ENDPOINT
        if challenge:
            base = API_CHALLENGE_ENDPOINT
        url = base + "/Locations/" + str(location_id)
        if endpoint:
            url += "/" + str(endpoint)
        return url

    async def _async_handle_on_backoff(self, _: dict[str, Any]) -> None:
        """Handle a backoff retry

        :param _: Unused
        :type _: dict[str, Any]
        """
        err_info = sys.exc_info()
        err: ClientResponseError = err_info[1].with_traceback(err_info[2])  # type: ignore

        if err.status in (401, 403):
            LOG.warning(f"Refreshing websocket token {err.request_info.url}")
            if (
                "client/negotiate" in str(err.request_info.url)
                and err.request_info.method == "POST"
            ):
                LOG.info(
                    "401 detected on websocket, refreshing websocket token. Old url: {self.ws_url} Old Token: {self.ws_token}"
                )
                LOG.info(f"401 detected on {err.request_info.url}")
                async with self._backoff_refresh_lock_ws:
                    await self.refresh_ws_token()
                    await self.get_websocket_params()
                return

    @staticmethod
    def _handle_on_giveup(_: dict[str, Any]) -> None:
        """ "Handle a give up after retries are exhausted.

        :param _: [description]
        :type _: dict[str, Any]
        :raises RequestError: [description]
        """
        err_info = sys.exc_info()
        err = err_info[1].with_traceback(err_info[2])  # type: ignore
        raise RequestError(err) from err

    def _wrap_request_method(self, request_retries: int) -> Callable:
        """Wrap the request method in backoff/retry logic

        :param request_retries: Number of retries
        :type request_retries: int
        :return: ``_async_request`` callback method
        :rtype: Callable
        """
        return cast(
            Callable,
            backoff.on_exception(
                backoff.expo,
                ClientResponseError,
                jitter=backoff.random_jitter,
                logger=LOG,
                max_tries=request_retries,
                on_backoff=self._async_handle_on_backoff,
                on_giveup=self._handle_on_giveup,
            )(self._async_request),
        )

    def disable_request_retries(self) -> None:
        """Disable the request retry mechanism."""
        self.async_request = self._wrap_request_method(1)

    def enable_request_retries(self) -> None:
        """Enable the request retry mechanism."""
        self.async_request = self._wrap_request_method(self._request_retries)

    async def _async_post_init(self) -> None:
        """Perform some post-init actions."""
        LOG.debug("Websocket postinit")
        await self._get_fid()
        await self._get_device_token()
        # await self.refresh_ws_token()
        # self.websocket = WebsocketClient(self)

        # Initialize WebsocketManager ic-dev21
        self.websocket_manager = WebsocketManager(
            self.session, self.async_request, self._state_yaml, set_state
        )
        await self.websocket_manager.initialize_websockets()

        # Create both websocket clients
        self.websocket = WebsocketClient(self.websocket_manager.devicehub)
        self.websocket2 = WebsocketClient(self.websocket_manager.challengehub)

    async def refresh_ws_token(self) -> None:
        """Refresh the websocket token."""
        await self.websocket_manager.refresh_token(self.websocket_manager.devicehub)
        await self.websocket_manager.refresh_token(self.websocket_manager.challengehub)

    async def post_devicehub_negociate(self) -> tuple[str, str]:
        LOG.debug("Getting websocket url")
        url = f"{AUTOMATION_DEVICEHUB_ENDPOINT}/negotiate"
        LOG.debug(f"devicehub URL is {url}")
        resp = await self.async_request("post", url)
        ws_url = resp.get("url")
        ws_token = resp.get("accessToken")
        LOG.debug("Calling set_state devicehub_negotiate")
        await set_state(
            self._state_yaml,
            "websocket",
            {
                "url": ws_url,
                "token": ws_token,
            },
        )
        return (ws_url, ws_token)

    async def get_websocket_params(self) -> None:
        uri = parse.urlparse(self.ws_url)
        LOG.debug("Getting websocket params")
        LOG.debug(f"Getting uri {uri}")
        resp: dict[str, Any] = await self.async_request(
            "post",
            f"{uri.path}negotiate?{uri.query}",
            host=uri.netloc,
            headers={
                "authorization": f"Bearer {self.ws_token}",
            },
        )
        conn_id: str = resp.get("connectionId", "")
        self.full_ws_url = f"{self.ws_url}&id={conn_id}&access_token={self.ws_token}"
        LOG.debug(f"Getting full ws URL {self.full_ws_url}")
        transport_dict: list[WebsocketTransportsDict] = resp.get(
            "availableTransports", []
        )
        websocket_dict: WebsocketDict = {
            "connection_id": conn_id,
            "available_transports": transport_dict,
            "full_ws_url": self.full_ws_url,
        }
        LOG.debug("Calling set_state websocket_params")
        await set_state(self._state_yaml, "websocket", websocket_dict)

    async def fb_install(self, fb_id: str) -> None:
        LOG.debug("Posting firebase install")
        body = {
            "fid": fb_id,
            "appId": FB_APP_ID,
            "authVersion": FB_AUTH_VERSION,
            "sdkVersion": FB_SDK_VERSION,
        }
        try:
            resp = await self._async_request(
                "post",
                FB_INSTALL_ENDPOINT,
                host=FB_INSTALL_HOSTNAME,
                headers=FB_INSTALL_HEADERS,
                json=body,
            )
        except ClientResponseError as err:
            LOG.error(f"ClientResponseError: {err}")
            if err.status in (401, 403):
                raise InvalidCredentialsError("Invalid credentials") from err
            raise RequestError(err) from err
        LOG.debug(f"FB Install data: {resp}")
        auth_token = resp.get("authToken", {})
        LOG.debug("Calling set_state fb_install")
        await set_state(
            self._state_yaml,
            "firebase",
            {
                "fid": resp.get("fid", ""),
                "name": resp.get("name", ""),
                "token": {
                    "access": auth_token.get("token"),
                    "refresh": resp.get("refreshToken"),
                    "expires_at": datetime.now()
                    + timedelta(seconds=int(auth_token.get("expiresIn").strip("s"))),
                },
            },
        )

    async def android_register(self) -> None:
        """Registers the device to GCM. This is required to establish a websocket"""
        LOG.debug("Posting android register")
        body: dict[str, Any] = ANDROID_CLIENT_POST
        body["X-appid"] = self._fb_fid
        body["X-Goog-Firebase-Installations-Auth"] = self._fb_auth_token
        parsed_body: str = parse.urlencode(body, safe="*")
        try:
            resp = await self._async_request(
                "post",
                ANDROID_CLIENT_ENDPOINT,
                host=ANDROID_CLIENT_HOSTNAME,
                headers=ANDROID_CLIENT_HEADERS,
                data=parsed_body,
            )
        except ClientResponseError as err:
            LOG.error(f"ClientResponseError: {err}")
            if err.status in (401, 403):
                raise InvalidCredentialsError("Invalid credentials") from err
            raise RequestError(err) from err
        LOG.debug(f"Android client register: {resp}")
        msg: str = resp.get("message", "")
        if msg.startswith("Error="):
            LOG.error(f"Android registration error: {msg}")
            raise RequestError
        token = msg.split("=")[-1]
        LOG.debug("Calling set_state android_register")
        await set_state(
            self._state_yaml,
            "android",
            {
                "token": token,
            },
        )

    async def get_location_id(self) -> int:
        url = f"{API_AUTOMATION_ENDPOINT}/Locations"
        LOG.debug(f"LocationId URL is {url}")
        req: list[dict[str, Any]] = await self.async_request("get", url)
        return int(req[0]["id"])

    async def get_devices(self, location_id: int) -> list[dict[str, Any]]:
        """Get list of all devices"""
        url = self._get_url("Devices", location_id)
        LOG.debug(f"Devices URL is {url}")
        devices: list[dict[str, Any]] = await self.async_request("get", url)
        devices.append(await self.get_gateway(location_id))
        # Now it's time to add devices coming from external sources like hass
        # integration.
        for callback in self._get_device_callbacks:
            devices.append(callback())
        return devices

    async def _set_device_attribute(
        self,
        device: HiloDevice,
        key: DeviceAttribute,
        value: Union[str, float, int, None],
    ) -> None:
        url = self._get_url(f"Devices/{device.id}/Attributes", device.location_id)
        LOG.debug(f"Device Attribute URL is {url}")
        await self.async_request("put", url, json={key.hilo_attribute: value})

    async def get_event_notifications(self, location_id: int) -> dict[str, Any]:
        """This will return events notifications
        Event types:
            203: Smoke detector test
        {
          "id": 123,
          "eventUid": null,
          "eventId": 456,
          "eventTypeId": 203,
          "userId": 123,
          "loginName": "something@microsoft.com",
          "locationId": 123,
          "deviceIdentifier": "me@me.com",
          "deviceId": 1234,
          "notificationDateUTC": "2022-01-02T16:05:02.6936251Z",
          "notificationTitle": "",
          "notificationBody": "Test manuel de l’alarme détecté.",
          "notificationCenterTitle": "",
          "notificationCenterBody": "Test manuel de l’alarme détecté.",
          "homePageNotificationTitle": "",
          "homePageNotificationBody": "Test manuel de l’alarme détecté.",
          "notificationDataJSON": "{\"NotificationType\":null,\"Title\":\"\",\"SubTitle\":null,\"Body\":\"Test manuel de l’alarme détecté.\",\"Badge\":0,\"Sound\":null,\"Data\":null,\"Tags\":null,\"Type\":\"TestDetected\",\"DeviceId\":324236,\"LocationId\":4051}",
          "viewed": false
        }"""
        url = self._get_url(None, location_id, events=True)
        LOG.debug(f"Event Notifications URL is {url}")
        return cast(dict[str, Any], await self.async_request("get", url))

    async def get_gd_events(
        self, location_id: int, event_id: int = 0
    ) -> dict[str, Any]:
        """This will return either all the future challenges or details about a specific
        challenge.
        {
          "currentPhase": null,
          "parameters": {
            "mode": "ambitious",
            "devices": [
              {
                "id": xxx,
                "deviceUid": "xxx",
                "name": "Thermostat XXX",
                "roomName": "Master bedroom",
                "optOut": false,
                "preheat": true
              },
          "consumption": {
            "currentWh": 4548.9404,
            "baselineWh": 14772.33,
            "estimatedReward": null,
            "baselineIntervals": [
              {
                "startTimeUtc": "2021-12-20T11:00:00Z",
                "baselineWh": 3180.1558
              },
              {
                "startTimeUtc": "2021-12-20T12:00:00Z",
                "baselineWh": 3589.4753
              },
              {
                "startTimeUtc": "2021-12-20T13:00:00Z",
                "baselineWh": 4168.0957
              },
              {
                "startTimeUtc": "2021-12-20T14:00:00Z",
                "baselineWh": 3834.6038
              }
            ]
          },
          "isPreSeason": false,
          "report": {
            "status": "Success",
            "reward": 5.63,
            "isMissingBaseline": false,
            "isMissingConsumption": false
          },
          "progress": "completed",
          "isParticipating": true,
          "isConfigurable": false,
          "id": xxx,
          "period": "am",
          "phases": {
            "preheatStartDateUTC": "2021-12-20T09:00:00Z",
            "preheatEndDateUTC": "2021-12-20T11:00:00Z",
            "reductionStartDateUTC": "2021-12-20T11:00:00Z",
            "reductionEndDateUTC": "2021-12-20T15:00:00Z",
            "recoveryStartDateUTC": "2021-12-20T15:00:00Z",
            "recoveryEndDateUTC": "2021-12-20T15:50:00Z"
          }
        }
        """

        url = self._get_url("Events", location_id, True)
        if not event_id:
            url += "?active=true"
        else:
            url += f"/{event_id}"

        LOG.debug(f"get_gd_events URL is {url}")
        return cast(dict[str, Any], await self.async_request("get", url))

    async def get_seasons(self, location_id: int) -> dict[str, Any]:
        """This will return the rewards and current season total
        https://api.hiloenergie.com/challenge/v1/api/Locations/XXXX/Seasons
        [
          {
            "season": 2021,
            "totalReward": 69420.13,
            "events": [
              {
                "id": 107,
                "startDateUtc": "2021-11-25T20:00:00Z",
                "period": "PM",
                "reward": 8.77,
                "status": "Success"
              },
            ]
          }
        ]
        """
        url = self._get_url("Seasons", location_id, challenge=True)
        LOG.debug(f"Seasons URL is {url}")
        return cast(dict[str, Any], await self.async_request("get", url))

    async def get_gateway(self, location_id: int) -> dict[str, Any]:
        url = self._get_url("Gateways/Info", location_id)
        LOG.debug(f"Gateway URL is {url}")
        req = await self.async_request("get", url)
        saved_attrs = [
            "zigBeePairingActivated",
            "zigBeeChannel",
            "firmwareVersion",
            "onlineStatus",
            "lastStatusTime",
            "disconnected",
        ]

        gw = {
            "name": "Hilo Gateway",
            "Disconnected": {"value": not req[0].get("onlineStatus") == "Online"},
            "type": "Gateway",
            "category": "Gateway",
            "supportedAttributes": ", ".join(saved_attrs),
            "settableAttributes": "",
            "id": 1,
            "identifier": req[0].get("dsn"),
            "sdi": req[0].get("sdi"),
            "provider": 1,
            "model_number": "EQ000017",
            "sw_version": req[0].get("firmwareVersion"),
        }
        for attr in saved_attrs:
            gw[attr] = {"value": req[0].get(attr)}
        return gw

    async def get_weather(self, location_id: int) -> dict[str, Any]:
        """This will return the current weather like in the app
        https://api.hiloenergie.com/Automation/v1/api/Locations/XXXX/Weather
        [
          {
            "temperature": -9.0,
            "time":"0001-01-01T00:00:00Z",
            "condition":"Foggy",
            "icon":0,
            "humidity":92.0
          }
        ]
        """
        url = self._get_url("Weather", location_id)
        LOG.debug(f"Weather URL is {url}")
        response = await self.async_request("get", url)
        LOG.debug(f"Weather API response: {response}")
        return cast(dict[str, Any], await self.async_request("get", url))
