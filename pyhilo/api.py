from __future__ import annotations

import asyncio
import base64
from datetime import datetime, timedelta
import hashlib
import json
import random
import string
import sys
from typing import Any, Callable, Union, cast
from urllib import parse

from aiohttp import ClientSession
from aiohttp.client_exceptions import ClientResponseError
import backoff
from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session
import httpx

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
    PLATFORM_HOST,
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
from pyhilo.websocket import WebsocketClient, WebsocketManager


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
        oauth_session: OAuth2Session,
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
        self.websocket_devices: WebsocketClient
        # Backward compatibility during transition to websocket for challenges. Currently the HA Hilo integration
        # uses the .websocket attribute. Re-added this attribute and point to the same object as websocket_devices.
        # Should be removed once the transition to the challenge websocket is completed everywhere.
        self.websocket: WebsocketClient
        self.websocket_challenges: WebsocketClient
        self.log_traces = log_traces
        self._get_device_callbacks: list[Callable[..., Any]] = []
        self.ws_url: str = ""
        self.ws_token: str = ""
        self.endpoint: str = ""
        self._urn: str | None = None
        self._websocket_device_cache: list[dict[str, Any]] = []
        self._device_cache_ready: asyncio.Event = asyncio.Event()

    @classmethod
    async def async_create(
        cls,
        *,
        session: ClientSession,
        oauth_session: OAuth2Session,
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

        access_token = str(self._oauth_session.token["access_token"])
        LOG.debug("Websocket access token is %s", access_token)

        urn = self.urn
        LOG.debug("Extracted URN: %s", urn)

        return str(self._oauth_session.token["access_token"])

    @property
    def urn(self) -> str | None:
        """Extract URN from the JWT access token."""
        if self._urn is not None:
            return self._urn

        try:
            if not self._oauth_session.valid_token:
                return None
            token = self._oauth_session.token["access_token"]
            payload_part = token.split(".")[1]
            # Add padding if necessary
            padding = 4 - len(payload_part) % 4
            if padding != 4:
                payload_part += "=" * padding

            decoded = base64.urlsafe_b64decode(payload_part)
            claims = json.loads(decoded)
            urn_claim = claims.get("urn:com:hiloenergie:profile:location_hilo_id")
            if urn_claim and isinstance(urn_claim, list) and len(urn_claim) > 0:
                self._urn = urn_claim[0]  # Get the first URN from the array
            else:
                self._urn = None

            return self._urn
        except (IndexError, json.JSONDecodeError, KeyError):
            LOG.error("Failed to extract URN from access token")
            return None

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
            (
                DeviceAttribute(attribute, HILO_READING_TYPES.get(value_type, "null"))
                if value_type
                else attribute
            ),
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

        if endpoint.startswith(AUTOMATION_CHALLENGE_ENDPOINT):
            # remove Ocp-Apim-Subscription-Key header to avoid 401 error (Thanks Leicas)
            kwargs["headers"].pop("Ocp-Apim-Subscription-Key", None)
            kwargs["headers"]["authorization"] = f"Bearer {access_token}"

        data: dict[str, Any] = {}
        url = parse.urljoin(f"https://{host}", endpoint)
        if self.log_traces:
            LOG.debug("[TRACE] Headers: %s", kwargs["headers"])
            LOG.debug("[TRACE] Async request: %s %s", method, url)

        async with self.session.request(method, url, **kwargs) as resp:
            if "application/json" in resp.headers.get("content-type", ""):
                try:
                    data = await resp.json(content_type=None)
                except json.decoder.JSONDecodeError:
                    LOG.warning("JSON Decode error: %s", resp.__dict__)
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
        gd: bool = False,
        drms: bool = False,
        events: bool = False,
        challenge: bool = False,
        location_id: Union[int, None] = None,
        urn: Union[str, None] = None,
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

        url = base + (f"/Locations/{urn}" if urn else f"/Locations/{location_id}")

        if endpoint:
            url += f"/{endpoint}"

        return url

    async def _async_handle_on_backoff(self, _: dict[str, Any]) -> None:
        """Handle a backoff retry

        :param _: Unused
        :type _: dict[str, Any]
        """
        err_info = sys.exc_info()
        err: ClientResponseError = err_info[1].with_traceback(err_info[2])  # type: ignore

        if err.status in (401, 403):
            LOG.warning("Refreshing websocket token %s", err.request_info.url)
            if (
                "client/negotiate" in str(err.request_info.url)
                and err.request_info.method == "POST"
            ):
                LOG.info(
                    "401 detected on websocket, refreshing websocket token. Old url: {self.ws_url} Old Token: {self.ws_token}"
                )
                LOG.info("401 detected on %s", err.request_info.url)
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
        LOG.debug("Websocket _async_post_init running")
        await self._get_fid()
        await self._get_device_token()

        # Initialize WebsocketManager ic-dev21
        self.websocket_manager = WebsocketManager(
            self.session, self.async_request, self._state_yaml, set_state, api=self
        )
        await self.websocket_manager.initialize_websockets()

        # Create both websocket clients
        # ic-dev21 need to work on this as it can't lint as is, may need to
        # instantiate differently
        # TODO: fix type ignore after refactor
        self.websocket_devices = WebsocketClient(self.websocket_manager.devicehub)  # type: ignore

        # For backward compatibility during the transition to challengehub websocket
        self.websocket = self.websocket_devices
        self.websocket_challenges = WebsocketClient(self.websocket_manager.challengehub)  # type: ignore

    async def refresh_ws_token(self) -> None:
        """Refresh the websocket token."""
        await self.websocket_manager.refresh_token(self.websocket_manager.devicehub)
        await self.websocket_manager.refresh_token(self.websocket_manager.challengehub)

    async def get_websocket_params(self) -> None:
        """Retrieves and constructs WebSocket connection parameters from the negotiation endpoint."""
        uri = parse.urlparse(self.ws_url)
        LOG.debug("Getting websocket params")
        LOG.debug("Getting uri %s", uri)
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
        LOG.debug("Getting full ws URL %s", self.full_ws_url)
        transport_dict: list[WebsocketTransportsDict] = resp.get(
            "availableTransports", []
        )
        websocket_dict: WebsocketDict = {
            "connection_id": conn_id,
            "available_transports": transport_dict,
            "full_ws_url": self.full_ws_url,
        }
        LOG.debug("Calling set_state from get_websocket_params")
        await set_state(self._state_yaml, "websocket", websocket_dict)

    async def fb_install(self, fb_id: str) -> None:
        """Registers a Firebase installation and stores the authentication token state."""
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
            LOG.error("ClientResponseError: %s", err)
            if err.status in (401, 403):
                raise InvalidCredentialsError("Invalid credentials") from err
            raise RequestError(err) from err
        LOG.debug("FB Install data: %s", resp)
        auth_token = resp.get("authToken", {})
        LOG.debug("Calling set_state from fb_install")
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
            LOG.error("ClientResponseError: %s", err)
            if err.status in (401, 403):
                raise InvalidCredentialsError("Invalid credentials") from err
            raise RequestError(err) from err
        LOG.debug("Android client register: %s", resp)
        msg: str = resp.get("message", "")
        if msg.startswith("Error="):
            LOG.error("Android registration error: %s", msg)
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

    async def get_location_ids(self) -> tuple[int, str]:
        """Gets location id from an API call"""
        url = f"{API_AUTOMATION_ENDPOINT}/Locations"
        LOG.debug("LocationId URL is %s", url)
        req: list[dict[str, Any]] = await self.async_request("get", url)
        return (req[0]["id"], req[0]["locationHiloId"])

    async def _call_graphql_query(
        self, query: str, variables: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute a GraphQL query and return the raw response data.

        This is a simplified helper that returns raw GraphQL data without
        going through the GraphqlValueMapper. Used for get_devices migration.

        Args:
            query: GraphQL query string
            variables: Query variables

        Returns:
            Raw GraphQL response data
        """
        access_token = await self.async_get_access_token()
        url = f"https://{PLATFORM_HOST}/api/digital-twin/v3/graphql"
        headers = {"Authorization": f"Bearer {access_token}"}

        query_hash = hashlib.sha256(query.encode("utf-8")).hexdigest()

        payload: dict[str, Any] = {
            "extensions": {
                "persistedQuery": {
                    "version": 1,
                    "sha256Hash": query_hash,
                }
            },
            "variables": variables,
        }

        async with httpx.AsyncClient(http2=True) as client:
            try:
                response = await client.post(url, json=payload, headers=headers)
                response_json = response.json()
            except Exception as e:
                LOG.error("Unexpected error calling GraphQL API: %s", e)
                raise

            # Handle Persisted Query Not Found error (can come as 400 status)
            if "errors" in response_json:
                for error in response_json["errors"]:
                    if error.get("message") == "PersistedQueryNotFound":
                        LOG.debug("Persisted query not found, retrying with full query")
                        payload["query"] = query
                        try:
                            response = await client.post(
                                url, json=payload, headers=headers
                            )
                            response.raise_for_status()
                            response_json = response.json()
                        except Exception as e:
                            LOG.error("Error parsing response on retry: %s", e)
                            raise
                        break
                else:
                    # Other GraphQL errors
                    LOG.error("GraphQL errors: %s", response_json["errors"])
                    raise Exception(f"GraphQL errors: {response_json['errors']}")
            elif response.status_code != 200:
                # Non-GraphQL error
                error_body = response.text
                LOG.error(
                    "GraphQL API returned status %d: %s",
                    response.status_code,
                    error_body,
                )
                response.raise_for_status()

            if "data" not in response_json:
                LOG.error("No data in GraphQL response: %s", response_json)
                raise Exception("No data in GraphQL response")

            return cast(dict[str, Any], response_json["data"])

    async def get_devices_graphql(self, location_hilo_id: str) -> list[dict[str, Any]]:
        """Get list of all devices using GraphQL.

        This replaces the REST endpoint /api/Locations/{LocationId}/Devices
        which is being deprecated.

        Uses the existing QUERY_GET_LOCATION from GraphQlHelper to avoid duplication.

        Args:
            location_hilo_id: The location Hilo ID (URN)

        Returns:
            List of device dictionaries in the same format as the REST endpoint
        """
        from pyhilo.graphql import GraphQlHelper

        # Use the existing comprehensive GraphQL query from GraphQlHelper
        query = GraphQlHelper.QUERY_GET_LOCATION

        # Call GraphQL using our helper
        data = await self._call_graphql_query(
            query, {"locationHiloId": location_hilo_id}
        )

        # Transform GraphQL response to REST format
        graphql_devices = data["getLocation"]["devices"]
        rest_devices = []

        for idx, gql_device in enumerate(graphql_devices, start=2):
            rest_device = self._transform_graphql_device_to_rest(gql_device, idx)
            if rest_device:
                rest_devices.append(rest_device)

        LOG.debug("Fetched %d devices via GraphQL", len(rest_devices))
        return rest_devices

    def _transform_graphql_device_to_rest(
        self, gql_device: dict[str, Any], device_id: int
    ) -> dict[str, Any] | None:
        """Transform a GraphQL device object to REST format.

        Args:
            gql_device: Device object from GraphQL
            device_id: Numeric device ID to assign

        Returns:
            Device dictionary in REST format, or None if device type is Gateway
            (Gateway is handled separately by get_gateway())
        """
        device_type = gql_device.get("deviceType", "Unknown")

        # Map GraphQL device types to REST device types
        type_mapping = {
            "Tstat": "Thermostat",
            "BasicThermostat": "Thermostat",
            "LowVoltageTstat": "Thermostat24V",
            "HeatingFloor": "FloorThermostat",
            "Cee": "Cee",
            "Ccr": "Ccr",
            "Switch": "LightSwitch",
            "BasicSwitch": "LightSwitch",
            "Dimmer": "LightDimmer",
            "BasicDimmer": "LightDimmer",
            "ColorBulb": "ColorBulb",
            "WhiteBulb": "WhiteBulb",
            "BasicLight": "WhiteBulb",
            "Meter": "Meter",
            "BasicSmartMeter": "Meter",
            "ChargingPoint": "ChargingPoint",
            "BasicEVCharger": "ChargingPoint",
            "BasicChargeController": "Ccr",
            "Hub": "Gateway",
        }

        rest_type = type_mapping.get(device_type, device_type)

        # Skip Gateway - it's fetched separately
        if rest_type == "Gateway":
            return None

        # Build the device dictionary
        rest_device = {
            "id": device_id,
            "hilo_id": gql_device.get("hiloId", ""),
            "identifier": gql_device.get("physicalAddress", ""),
            "type": rest_type,
            "name": gql_device.get(
                "name", f"{rest_type} {device_id}"
            ),  # Use GraphQL name or fallback
            "category": rest_type,
            "supportedAttributes": "",
            "settableAttributes": "",
            "provider": 1,
        }

        # Add all attributes from GraphQL device
        supported_attrs = []
        settable_attrs = []

        # Common attributes
        if "connectionStatus" in gql_device:
            rest_device["Disconnected"] = {"value": gql_device["connectionStatus"] == 2}
            supported_attrs.append("Disconnected")

        if "power" in gql_device and gql_device["power"]:
            rest_device["Power"] = {"value": gql_device["power"].get("value", 0)}
            supported_attrs.append("Power")

        # Thermostat attributes
        if "ambientTemperature" in gql_device and gql_device["ambientTemperature"]:
            rest_device["CurrentTemperature"] = {
                "value": gql_device["ambientTemperature"].get("value", 0)
            }
            supported_attrs.append("CurrentTemperature")

        if "ambientTempSetpoint" in gql_device and gql_device["ambientTempSetpoint"]:
            rest_device["TargetTemperature"] = {
                "value": gql_device["ambientTempSetpoint"].get("value", 0)
            }
            supported_attrs.append("TargetTemperature")
            settable_attrs.append("TargetTemperature")

        if "ambientHumidity" in gql_device:
            rest_device["CurrentHumidity"] = {"value": gql_device["ambientHumidity"]}
            supported_attrs.append("CurrentHumidity")

        if "mode" in gql_device:
            rest_device["Mode"] = {"value": gql_device["mode"]}
            supported_attrs.append("Mode")
            settable_attrs.append("Mode")

        if "gDState" in gql_device:
            rest_device["GDState"] = {"value": gql_device["gDState"]}
            supported_attrs.append("GDState")

        # Light/Switch attributes
        if "state" in gql_device:
            rest_device["OnOff"] = {"value": gql_device["state"]}
            supported_attrs.append("OnOff")
            settable_attrs.append("OnOff")

        if "level" in gql_device:
            rest_device["Intensity"] = {"value": gql_device["level"]}
            supported_attrs.append("Intensity")
            settable_attrs.append("Intensity")

        if "hue" in gql_device:
            rest_device["Hue"] = {"value": gql_device["hue"]}
            supported_attrs.append("Hue")
            settable_attrs.append("Hue")

        if "saturation" in gql_device:
            rest_device["Saturation"] = {"value": gql_device["saturation"]}
            supported_attrs.append("Saturation")
            settable_attrs.append("Saturation")

        if "colorTemperature" in gql_device:
            rest_device["ColorTemperature"] = {"value": gql_device["colorTemperature"]}
            supported_attrs.append("ColorTemperature")
            settable_attrs.append("ColorTemperature")

        # Version info
        if "version" in gql_device:
            rest_device["sw_version"] = gql_device["version"]

        # Set the attributes strings
        rest_device["supportedAttributes"] = ", ".join(supported_attrs)
        rest_device["settableAttributes"] = ", ".join(settable_attrs)

        return rest_device

    async def get_devices(self, location_id: int) -> list[dict[str, Any]]:
        """Get list of all devices.

        Prioritizes websocket-cached device data (from DeviceListInitialValuesReceived)
        over REST/GraphQL since the websocket provides everything we need.
        Falls back to GraphQL, then REST if websocket data unavailable.
        """
        devices: list[dict[str, Any]] = []

        # Try to use cached websocket device data first
        # The DeviceHub websocket sends DeviceListInitialValuesReceived with full device info
        if self._websocket_device_cache:
            LOG.debug("Using cached device list from websocket (%d devices)", len(self._websocket_device_cache))
            devices = self._websocket_device_cache.copy()
        # Try GraphQL if we have a URN and no websocket cache
        elif self.urn:
            try:
                LOG.debug("Fetching devices via GraphQL for URN: %s", self.urn)
                devices = await self.get_devices_graphql(self.urn)

                # WORKAROUND: Fetch REST device IDs for attribute setting
                # This is needed because the attribute endpoint still uses numeric IDs
                try:
                    url = self._get_url("Devices", location_id=location_id)
                    rest_devices = await self.async_request("get", url)

                    # Build mapping of identifier -> numeric id
                    id_mapping = {
                        d.get("identifier"): d.get("id")
                        for d in rest_devices
                        if d.get("identifier")
                    }

                    # Update GraphQL devices with real REST IDs
                    for device in devices:
                        identifier = device.get("identifier")
                        if identifier in id_mapping:
                            device["id"] = id_mapping[identifier]
                            LOG.debug(
                                "Mapped device %s to ID %d", identifier, device["id"]
                            )

                except Exception as e:
                    LOG.warning("Failed to fetch device ID mapping from REST: %s", e)
                    # Continue without mapping - devices will work read-only

            except Exception as e:
                LOG.warning("GraphQL device fetch failed, falling back to REST: %s", e)
                # Fallback to REST
                url = self._get_url("Devices", location_id=location_id)
                LOG.debug("Devices URL is %s", url)
                devices = await self.async_request("get", url)
        else:
            # No URN available, use REST
            LOG.debug("No URN available, using REST endpoint")
            url = self._get_url("Devices", location_id=location_id)
            LOG.debug("Devices URL is %s", url)
            devices = await self.async_request("get", url)

        # Add gateway device (still uses REST endpoint)
        devices.append(await self.get_gateway(location_id))

        # Add devices from external callbacks
        for callback in self._get_device_callbacks:
            devices.append(callback())

        return devices
    
    def cache_websocket_devices(self, device_list: list[dict[str, Any]]) -> None:
        """Cache device list received from DeviceHub websocket.
        
        The DeviceListInitialValuesReceived message contains the full device list
        with all the info we need (id, name, identifier, etc.) in REST format.
        This eliminates the need to call the deprecated REST endpoint.
        
        Args:
            device_list: List of devices from DeviceListInitialValuesReceived
        """
        self._websocket_device_cache = device_list
        self._device_cache_ready.set()
        LOG.debug("Cached %d devices from websocket", len(device_list))
    
    async def wait_for_device_cache(self, timeout: float = 10.0) -> bool:
        """Wait for the websocket device cache to be populated.
        
        This should be called before devices.async_init() to ensure
        device names and IDs are available from the websocket.
        
        Args:
            timeout: Maximum time to wait in seconds (default: 10.0)
            
        Returns:
            True if cache was populated, False if timeout occurred
        """
        import time
        start_time = time.time()
        LOG.debug("Waiting for websocket device cache (timeout: %.1fs)...", timeout)
        
        try:
            await asyncio.wait_for(self._device_cache_ready.wait(), timeout=timeout)
            elapsed = time.time() - start_time
            LOG.debug("Device cache ready after %.2f seconds", elapsed)
            return True
        except asyncio.TimeoutError:
            elapsed = time.time() - start_time
            LOG.warning(
                "Timeout waiting for websocket device cache after %.2f seconds, will use fallback method",
                elapsed
            )
            return False

    async def _set_device_attribute(
        self,
        device: HiloDevice,
        key: DeviceAttribute,
        value: Union[str, float, int, None],
    ) -> None:
        """Sets device attributes"""
        url = self._get_url(
            f"Devices/{device.id}/Attributes", location_id=device.location_id
        )
        LOG.debug("Device Attribute URL is %s", url)
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
        url = self._get_url(None, events=True, location_id=location_id)
        LOG.debug("Event Notifications URL is %s", url)
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
        # ic-dev21 need to check but this is probably dead code
        url = self._get_url("Events", True, location_id=location_id)
        if not event_id:
            url += "?active=true"
        else:
            url += f"/{event_id}"

        LOG.debug("get_gd_events URL is %s", url)
        return cast(dict[str, Any], await self.async_request("get", url))

    # keep location_id for now for backward compatibility with existing hilo branch
    async def get_seasons(self, location_id: int) -> list[dict[str, Any]]:
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
        url = self._get_url("seasonssummary", challenge=True, urn=self.urn)
        LOG.debug("Seasons URL is %s", url)

        seasons = await self.async_request("get", url)
        LOG.debug("Seasons API response: %s", seasons)

        all_seasons: list[dict[str, Any]] = []

        for season_data in seasons:
            season = season_data.get("season")
            ratePlan = season_data.get("ratePlan")
            periodId = season_data.get("periodId")

            url = self._get_url(
                f"rates/{ratePlan}/seasons/{season}/events?periodId={periodId}",
                challenge=True,
                urn=self.urn,
            )
            LOG.debug("Seasons Events URL is %s", url)
            season_events = await self.async_request("get", url)
            LOG.debug("Season %s Events API response: %s", season, season_events)
            all_seasons.append(season_events)

        return all_seasons

    async def get_gateway(self, location_id: int) -> dict[str, Any]:
        """Gets info about the Hilo hub (gateway)"""
        url = self._get_url("Gateways/Info", location_id=location_id)
        LOG.debug("Gateway URL is %s", url)
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
        url = self._get_url("Weather", location_id=location_id)
        LOG.debug("Weather URL is %s", url)
        response = await self.async_request("get", url)
        LOG.debug("Weather API response: %s", response)
        return cast(dict[str, Any], response)