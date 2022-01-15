from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import json
import random
import string
import sys
from typing import TYPE_CHECKING, Any, Callable, Union, cast
from urllib import parse

from aiohttp import ClientSession
from aiohttp.client_exceptions import ClientResponseError
import backoff

from pyhilo.const import (
    ANDROID_CLIENT_ENDPOINT,
    ANDROID_CLIENT_HEADERS,
    ANDROID_CLIENT_HOSTNAME,
    ANDROID_CLIENT_POST,
    API_AUTOMATION_ENDPOINT,
    API_GD_SERVICE_ENDPOINT,
    API_HOSTNAME,
    API_REGISTRATION_ENDPOINT,
    API_REGISTRATION_HEADERS,
    AUTH_CLIENT_ID,
    AUTH_ENDPOINT,
    AUTH_HOSTNAME,
    AUTH_RESPONSE_TYPE,
    AUTH_SCOPE,
    AUTH_TYPE_PASSWORD,
    AUTH_TYPE_REFRESH,
    AUTOMATION_DEVICEHUB_ENDPOINT,
    AUTOMATION_HOSTNAME,
    CONTENT_TYPE_FORM,
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
from pyhilo.util import schedule_callback
from pyhilo.util.state import (
    RegistrationDict,
    TokenDict,
    WebsocketDict,
    WebsocketTransportsDict,
    get_state,
    set_state,
)
from pyhilo.websocket import WebsocketClient


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
        request_retries: int = REQUEST_RETRY,
    ) -> None:
        """Initialize"""
        self._access_token: str | None = None
        self._backoff_refresh_lock_api = asyncio.Lock()
        self._backoff_refresh_lock_ws = asyncio.Lock()
        self._reg_id: str | None = None
        self._request_retries = request_retries
        self._state_yaml: str = DEFAULT_STATE_FILE
        self._token_expiration: datetime | None = None
        self.async_request = self._wrap_request_method(self._request_retries)
        self.device_attributes = get_device_attributes()
        self.session: ClientSession = session
        self.websocket: WebsocketClient
        self._username: str
        self._refresh_token_callbacks: list[Callable[..., Any]] = []
        self.log_traces: bool = False
        self._get_device_callbacks: list[Callable[..., Any]] = []

    @property
    def headers(self) -> dict[str, Any]:
        headers = {
            "User-Agent": DEFAULT_USER_AGENT,
        }
        if not self._access_token:
            return headers
        return {
            **headers,
            **{
                "Content-Type": "application/json; charset=utf-8",
                "Ocp-Apim-Subscription-Key": SUBSCRIPTION_KEY,
                "authorization": f"Bearer {self._access_token}",
            },
        }

    @classmethod
    async def async_auth_refresh_token(
        cls,
        *,
        session: ClientSession,
        provided_refresh_token: Union[str, None] = None,
        request_retries: int = REQUEST_RETRY,
        state_yaml: str = DEFAULT_STATE_FILE,
        log_traces: bool = False,
    ) -> API:
        api = cls(session=session, request_retries=request_retries)
        api.log_traces = log_traces
        api._state_yaml = state_yaml
        api.state = get_state(state_yaml)
        if provided_refresh_token:
            api._refresh_token = provided_refresh_token
        else:
            token_state = api.state.get("token", {})
            api._refresh_token = token_state.get("refresh")
        if not api._refresh_token:
            raise InvalidCredentialsError

        await api._async_refresh_access_token()
        await api._async_post_init()
        return api

    @classmethod
    async def async_auth_password(
        cls,
        username: str,
        password: str,
        *,
        session: ClientSession,
        request_retries: int = REQUEST_RETRY,
        state_yaml: str = DEFAULT_STATE_FILE,
        log_traces: bool = False,
    ) -> API:
        """Get an authenticated API object from a username and password.
        :param username: the username
        :type username: ``str``
        :param password: the password
        :type the password: ``str``
        :param session: The ``aiohttp`` ``ClientSession`` session used for all HTTP requests
        :type session: ``aiohttp.client.ClientSession``
        :param request_retries: The default number of request retries to use
        :type request_retries: ``int``
        :param state_yaml: File where we store registration ID
        :type state_yaml: ``str``
        :rtype: :meth:`pyhilo.api.API`
        """
        api = cls(session=session, request_retries=request_retries)
        api.log_traces = log_traces
        api._username = username
        api._state_yaml = state_yaml
        api.state = get_state(state_yaml)
        token_state = api.state.get("token", {})
        token_expiration = (
            token_state.get("expires_at", datetime.now()) or datetime.now()
        )
        refresh_token = token_state.get("refresh")
        if datetime.now() < token_expiration:
            api._access_token = token_state.get("access")
            api._refresh_token = token_state.get("refresh")
            api._access_token_expire_dt = token_state.get("expires_at", datetime.now())
            LOG.info(
                f"Saved state token seems valid and expires on {api._access_token_expire_dt}"
            )
        elif refresh_token:
            api._refresh_token = refresh_token
            await api._async_refresh_access_token()
        else:
            password = parse.quote(password, safe="!@#$%^&*()")
            auth_body = api.auth_body(
                AUTH_TYPE_PASSWORD, username=username, password=password
            )
            await api.async_auth_post(auth_body)
        await api._async_post_init()
        return api

    def dev_atts(
        self, attribute: str, value_type: Union[str, None] = None
    ) -> Union[DeviceAttribute, None]:
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
            DeviceAttribute(attribute, HILO_READING_TYPES.get(value_type, ""))
            if value_type
            else None,
        )

    def _get_fid_state(self) -> bool:
        """Looks up the cached state to define the firebase attributes
        on the API instances.

        :return: Whether or not we have cached firebase state
        :rtype: bool
        """
        self.state = get_state(self._state_yaml)
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

    def _get_android_state(self) -> bool:
        """Looks up the cached state to define the android device token
        on the API instances.

        :return: Whether or not we have cached android state
        :rtype: bool
        """
        self.state = get_state(self._state_yaml)
        android_state = self.state.get("android", {})
        if token := android_state.get("token"):
            self._device_token = token
            return True
        return False

    async def _get_device_token(self) -> None:
        """Retrieves the android token if it's not cached."""
        if not self._get_android_state():
            await self.android_register()

    async def _get_fid(self) -> None:
        """Retrieves the firebase state if it's not cached."""
        if not self._get_fid_state():
            self._fb_id = "".join(
                random.SystemRandom().choice(string.ascii_letters + string.digits)
                for _ in range(FB_ID_LEN)
            )
            await self.fb_install(self._fb_id)
            self._get_fid_state()

    async def _async_refresh_access_token(self) -> None:
        """Update access/refresh tokens from a refresh token
        and schedule a callback for later to refresh it.
        """
        auth_body = self.auth_body(
            AUTH_TYPE_REFRESH,
            refresh_token=self._refresh_token,
        )
        await self.async_auth_post(auth_body)
        for callback in self._refresh_token_callbacks:
            schedule_callback(callback, self._refresh_token)

    async def async_auth_post(self, body: dict) -> None:
        """Prepares an authentication request for the Web API.

        :param body: Contains the parameters passed to get tokens
        :type body: dict
        :raises InvalidCredentialsError: Invalid username/password
        :raises RequestError: Other error
        """
        try:
            LOG.debug("Authentication intiated")
            resp = await self._async_request(
                "post",
                AUTH_ENDPOINT,
                host=AUTH_HOSTNAME,
                headers={
                    "Content-Type": CONTENT_TYPE_FORM,
                },
                data=body,
            )
        except ClientResponseError as err:
            LOG.error(f"ClientResponseError: {err}")
            if err.status in (401, 403):
                raise InvalidCredentialsError("Invalid credentials") from err
            raise RequestError(err) from err
        self._access_token = resp.get("access_token")
        self._access_token_expire_dt = datetime.now() + timedelta(
            seconds=int(str(resp.get("expires_in")))
        )
        self._refresh_token = resp.get(AUTH_TYPE_REFRESH, "")
        token_dict: TokenDict = {
            "access": self._access_token,
            "refresh": self._refresh_token,
            "expires_at": self._access_token_expire_dt,
        }
        set_state(self._state_yaml, "token", token_dict)

    def auth_body(
        self,
        grant_type: str,
        *,
        username: str = "",
        password: str = "",
        refresh_token: str = "",
    ) -> dict[Any, Any]:
        """Generates a dict to pass to the authentication endpoint for
        the Web API.

        :param grant_type: either password or refresh_token
        :type grant_type: str
        :param username: defaults to ""
        :type username: str, optional
        :param password: defaults to ""
        :type password: str, optional
        :param refresh_token: Refresh token received from a previous password auth, defaults to ""
        :type refresh_token: str, optional
        :return: Dict structured for authentication
        :rtype: dict[Any, Any]
        """
        LOG.debug(f"Auth body for grant {grant_type}")
        body = {
            "grant_type": grant_type,
            "client_id": AUTH_CLIENT_ID,
            "scope": AUTH_SCOPE,
        }
        if grant_type == AUTH_TYPE_PASSWORD:
            body = {
                **body,
                **{
                    "response_type": AUTH_RESPONSE_TYPE,
                    "username": username,
                    "password": password,
                },
            }
        elif grant_type == AUTH_TYPE_REFRESH:
            body[AUTH_TYPE_REFRESH] = refresh_token
        return body

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
        if endpoint.startswith(API_REGISTRATION_ENDPOINT):
            kwargs["headers"] = {**kwargs["headers"], **API_REGISTRATION_HEADERS}
        if endpoint.startswith(FB_INSTALL_ENDPOINT):
            kwargs["headers"] = {**kwargs["headers"], **FB_INSTALL_HEADERS}
        if endpoint.startswith(ANDROID_CLIENT_ENDPOINT):
            kwargs["headers"] = {**kwargs["headers"], **ANDROID_CLIENT_HEADERS}
        kwargs["headers"]["Host"] = host
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
        self, endpoint: str, location_id: int, gd: bool = False, drms: bool = False
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
        :return: Path to the requested endpoint
        :rtype: str
        """
        base = API_AUTOMATION_ENDPOINT
        if gd:
            base = API_GD_SERVICE_ENDPOINT
        if drms:
            base += "/DRMS"
        return base + "/Locations/" + str(location_id) + "/" + str(endpoint)

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
                async with self._backoff_refresh_lock_ws:
                    (self.ws_url, self.ws_token) = await self.post_devicehub_negociate()
                    await self.get_websocket_params()
                return
            if TYPE_CHECKING:
                assert self._access_token_expire_dt
            async with self._backoff_refresh_lock_api:
                if datetime.now() <= self._access_token_expire_dt:
                    return
                LOG.info("401 detected on api; refreshing api token")
                await self._async_refresh_access_token()

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

    def add_refresh_token_callback(
        self, callback: Callable[..., None]
    ) -> Callable[..., None]:
        """Add a callback that should be triggered when tokens are refreshed.
        Note that callbacks should expect to receive a refresh token as a parameter.
        :param callback: The method to call after receiving an event.
        :type callback: ``Callable[..., None]``
        """
        self._refresh_token_callbacks.append(callback)

        def remove() -> None:
            """Remove the callback."""
            self._refresh_token_callbacks.remove(callback)

        return remove

    async def _async_post_init(self) -> None:
        """Perform some post-init actions."""
        LOG.debug("Websocket postinit")
        await self._get_fid()
        await self._get_device_token()
        await self.refresh_ws_token()
        self.websocket = WebsocketClient(self)

    async def refresh_ws_token(self) -> None:
        reg_state = self.state.get("registration", {})
        android_state = self.state.get("android", {})
        if reg_id := reg_state.get("reg_id"):
            await self.delete_registration(reg_id)
        self._reg_id = await self.post_registration()
        reg_dict: RegistrationDict = {"reg_id": self._reg_id}
        set_state(self._state_yaml, "registration", reg_dict)
        (self.ws_url, self.ws_token) = await self.post_devicehub_negociate()
        await self.get_websocket_params()
        await self.put_registration(self._reg_id, android_state.get("token", ""))

    async def delete_registration(self, reg_id: str) -> None:
        LOG.debug(f"Deleting registration {reg_id}")
        url = f"{API_REGISTRATION_ENDPOINT}/{reg_id}"
        await self.async_request("delete", url)

    async def post_registration(self) -> str:
        LOG.debug("Requesting new registration")
        url = f"{API_REGISTRATION_ENDPOINT}"
        resp: dict[str, Any] = await self.async_request(
            "post",
            url,
            headers={
                **self.headers,
                **{
                    "Content-Type": "text/plain",
                    "Content-Length": "0",
                    "Accept": "text/plain",
                },
            },
        )
        return resp.get("message", "")

    async def put_registration(self, reg_id: str, handler: str) -> str:
        LOG.debug("Submitting handler for registration")
        url = f"{API_REGISTRATION_ENDPOINT}/{reg_id}"
        resp: dict[str, Any] = await self.async_request(
            "put", url, json={"platform": "fcm", "handle": handler}
        )
        return resp.get("message", "")

    async def post_devicehub_negociate(self) -> tuple[str, str]:
        LOG.debug("Getting websocket url")
        url = f"{AUTOMATION_DEVICEHUB_ENDPOINT}/negotiate"
        resp = await self.async_request("post", url, host=AUTOMATION_HOSTNAME)
        ws_url = resp.get("url")
        ws_token = resp.get("accessToken")
        set_state(
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
        transport_dict: list[WebsocketTransportsDict] = resp.get(
            "availableTransports", []
        )
        websocket_dict: WebsocketDict = {
            "connection_id": conn_id,
            "available_transports": transport_dict,
            "full_ws_url": self.full_ws_url,
        }
        set_state(self._state_yaml, "websocket", websocket_dict)

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
        set_state(
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
        set_state(
            self._state_yaml,
            "android",
            {
                "token": token,
            },
        )

    async def get_location_id(self) -> int:
        url = f"{API_AUTOMATION_ENDPOINT}/Locations"
        req: list[dict[str, Any]] = await self.async_request("get", url)
        return int(req[0]["id"])

    async def get_devices(self, location_id: int) -> list[dict[str, Any]]:
        """Get list of all devices"""
        url = self._get_url("Devices", location_id)
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
        await self.async_request("put", url, json={key.hilo_attribute: value})

    async def get_events(self, location_id: int, event_id: int = 0) -> dict[str, Any]:
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
        return cast(dict[str, Any], await self.async_request("get", url))

    async def get_seasons(self, location_id: int) -> dict[str, Any]:
        """This will return the rewards and current season total
        https://apim.hiloenergie.com/Automation/v1/api/DRMS/Locations/XXXX/Seasons
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
        url = self._get_url("Seasons", location_id, drms=True)
        return cast(dict[str, Any], await self.async_request("get", url))

    async def get_gateway(self, location_id: int) -> dict[str, Any]:
        url = self._get_url("Gateways/Info", location_id)
        req = await self.async_request("get", url)
        saved_attrs = [
            "zigBeePairingActivated",
            "zigBeeChannel",
            "firmwareVersion",
            "onlineStatus",
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
            "provider": 1,
            "model_number": "EQ000017",
            "sw_version": req[0].get("firmwareVersion"),
        }
        for attr in saved_attrs:
            gw[attr] = {"value": req[0].get(attr)}
        return gw
