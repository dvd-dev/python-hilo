import asyncio
import hashlib
import json
import logging
from typing import Any, Callable, Dict, List, Optional

import httpx
from httpx_sse import aconnect_sse

from pyhilo import API
from pyhilo.const import LOG, PLATFORM_HOST
from pyhilo.device.graphql_value_mapper import GraphqlValueMapper
from pyhilo.devices import Devices


class GraphQlHelper:
    """The GraphQl Helper class."""

    def __init__(self, api: API, devices: Devices):
        self._api = api
        self._devices = devices
        self.mapper: GraphqlValueMapper = GraphqlValueMapper()

        self.subscriptions: List[Optional[asyncio.Task]] = [None]

    async def async_init(self) -> None:
        """Initialize the Hilo "GraphQlHelper" class."""
        await self.call_get_location_query(self._devices.location_hilo_id)

    QUERY_GET_LOCATION: str = """query getLocation($locationHiloId: String!) {
                getLocation(id:$locationHiloId) {
                    hiloId
                    lastUpdate
                    lastUpdateVersion
                    devices {
                        deviceType
                        hiloId
                        physicalAddress
                        connectionStatus
                        ... on Gateway {
                            connectionStatus
                            controllerSoftwareVersion
                            lastConnectionTime
                            willBeConnectedToSmartMeter
                            zigBeeChannel
                            zigBeePairingModeEnhanced
                            smartMeterZigBeeChannel
                            smartMeterPairingStatus
                        }
                        ... on BasicSmartMeter {
                            deviceType
                            hiloId
                            physicalAddress
                            connectionStatus
                            zigBeeChannel
                            power {
                                value
                                kind
                            }
                        }
                        ... on LowVoltageThermostat {
                            coolTempSetpoint {
                                value
                            }
                            fanMode
                            fanSpeed
                            mode
                            currentState
                            power {
                                value
                                kind
                            }
                            ambientHumidity
                            gDState
                            ambientTemperature {
                                value
                                kind
                            }
                            ambientTempSetpoint {
                                value
                                kind
                            }
                            version
                            zigbeeVersion
                            connectionStatus
                            maxAmbientCoolSetPoint {
                                value
                                kind
                            }
                            minAmbientCoolSetPoint {
                                value
                                kind
                            }
                            maxAmbientTempSetpoint {
                                value
                                kind
                            }
                            minAmbientTempSetpoint {
                                value
                                kind
                            }
                            allowedModes
                            fanAllowedModes
                        }
                        ... on BasicSwitch {
                            deviceType
                            hiloId
                            physicalAddress
                            connectionStatus
                            state
                            power {
                                value
                                kind
                            }
                        }
                        ... on BasicLight {
                            deviceType
                            hiloId
                            physicalAddress
                            connectionStatus
                            state
                            hue
                            level
                            saturation
                            colorTemperature
                            lightType
                        }
                        ... on BasicEVCharger {
                            deviceType
                            hiloId
                            physicalAddress
                            connectionStatus
                            status
                            power {
                                value
                                kind
                            }
                        }
                        ... on BasicChargeController {
                            deviceType
                            hiloId
                            physicalAddress
                            connectionStatus
                            gDState
                            version
                            zigbeeVersion
                            state
                            power {
                                value
                                kind
                            }
                            ccrMode,
                            ccrAllowedModes
                        }
                        ... on HeatingFloorThermostat {
                            deviceType
                            hiloId
                            physicalAddress
                            connectionStatus
                            ambientHumidity
                            gDState
                            version
                            zigbeeVersion
                            thermostatType
                            physicalAddress
                            floorMode
                            power {
                                value
                                kind
                            }
                            ambientTemperature {
                                value
                                kind
                            }
                            ambientTempSetpoint {
                                value
                                kind
                            }
                            maxAmbientTempSetpoint {
                                value
                                kind
                            }
                            minAmbientTempSetpoint {
                                value
                                kind
                            }
                            floorLimit {
                                value
                            }
                        }
                        ... on WaterHeater {
                            deviceType
                            hiloId
                            physicalAddress
                            connectionStatus
                            gDState
                            version
                            probeTemp {
                                value
                                kind
                            }
                            zigbeeVersion
                            state
                            ccrType
                            alerts
                            power {
                                value
                                kind
                            }
                        }
                        ... on BasicDimmer {
                            deviceType
                            hiloId
                            physicalAddress
                            connectionStatus
                            state
                            level
                            power {
                                value
                                kind
                            }
                        }
                        ... on BasicThermostat {
                            deviceType
                            hiloId
                            physicalAddress
                            connectionStatus
                            ambientHumidity
                            gDState
                            version
                            zigbeeVersion
                            ambientTemperature {
                                value
                                kind
                            }
                            ambientTempSetpoint {
                                value
                                kind
                            }
                            maxAmbientTempSetpoint {
                                value
                                kind
                            }
                            minAmbientTempSetpoint {
                                value
                                kind
                            }
                            maxAmbientTempSetpointLimit {
                                value
                                kind
                            }
                            minAmbientTempSetpointLimit {
                                value
                                kind
                            }
                            heatDemand
                            power {
                                value
                                kind
                            }
                            mode
                            allowedModes
                        }
                    }
                }
    }"""

    SUBSCRIPTION_DEVICE_UPDATED: str = """subscription onAnyDeviceUpdated($locationHiloId: String!) {
    onAnyDeviceUpdated(locationHiloId: $locationHiloId) {
        deviceType
        locationHiloId
        transmissionTime
        operationId
        status
        device {
            ... on Gateway {
                connectionStatus
                controllerSoftwareVersion
                lastConnectionTime
                willBeConnectedToSmartMeter
                zigBeeChannel
                zigBeePairingModeEnhanced
                smartMeterZigBeeChannel
                smartMeterPairingStatus
            }
            ... on BasicSmartMeter {
                deviceType
                hiloId
                physicalAddress
                connectionStatus
                zigBeeChannel
                power {
                    value
                    kind
                }
            }
            ... on LowVoltageThermostat {
                deviceType
                hiloId
                physicalAddress
                  coolTempSetpoint {
                    value
                  }
                  fanMode
                  fanSpeed
                  mode
                  currentState
                  power {
                    value
                    kind
                  }
                  ambientHumidity
                  gDState
                  ambientTemperature {
                    value
                    kind
                  }
                  ambientTempSetpoint {
                    value
                    kind
                  }
                  version
                  zigbeeVersion
                  connectionStatus
                  maxAmbientCoolSetPoint {
                     value
                     kind
                  }
                minAmbientCoolSetPoint {
                  value
                    kind
                }
                maxAmbientTempSetpoint {
                    value
                    kind
                }
                minAmbientTempSetpoint {
                    value
                    kind
                }
                allowedModes
                fanAllowedModes
            }
            ... on BasicSwitch {
                deviceType
                hiloId
                physicalAddress
                connectionStatus
                state
                power {
                    value
                    kind
                }
            }
            ... on BasicLight {
                deviceType
                hiloId
                physicalAddress
                connectionStatus
                state
                hue
                level
                saturation
                colorTemperature
                lightType
            }
            ... on BasicEVCharger {
                deviceType
                hiloId
                physicalAddress
                connectionStatus
                status
                power {
                    value
                    kind
                }
            }
            ... on BasicChargeController {
                deviceType
                hiloId
                physicalAddress
                connectionStatus
                gDState
                version
                zigbeeVersion
                state
                power {
                    value
                    kind
                }
                ccrMode,
                ccrAllowedModes
            }
            ... on HeatingFloorThermostat {
                deviceType
                hiloId
                physicalAddress
                connectionStatus
                ambientHumidity
                gDState
                version
                zigbeeVersion
                thermostatType
                physicalAddress
                floorMode
                power {
                    value
                    kind
                }
                ambientTemperature {
                    value
                    kind
                }
                ambientTempSetpoint {
                    value
                    kind
                }
                maxAmbientTempSetpoint {
                    value
                    kind
                }
                minAmbientTempSetpoint {
                    value
                    kind
                }
                floorLimit {
                    value
                }
            }
            ... on WaterHeater {
                deviceType
                hiloId
                physicalAddress
                connectionStatus
                gDState
                version
                probeTemp {
                    value
                    kind
                }
                zigbeeVersion
                state
                ccrType
                alerts
                power {
                    value
                    kind
                }
            }
            ... on BasicDimmer {
                deviceType
                hiloId
                physicalAddress
                connectionStatus
                state
                level
                power {
                    value
                    kind
                }
            }
            ... on BasicThermostat {
                deviceType
                hiloId
                physicalAddress
                connectionStatus
                ambientHumidity
                gDState
                version
                zigbeeVersion
                ambientTemperature {
                    value
                    kind
                }
                ambientTempSetpoint {
                    value
                    kind
                }
                maxAmbientTempSetpoint {
                    value
                    kind
                }
                minAmbientTempSetpoint {
                    value
                    kind
                }
                maxAmbientTempSetpointLimit {
                    value
                    kind
                }
                minAmbientTempSetpointLimit {
                    value
                    kind
                }
                heatDemand
                power {
                    value
                    kind
                }
                mode
                allowedModes
            }
        }
    }
}"""

    SUBSCRIPTION_LOCATION_UPDATED: str = """subscription onAnyLocationUpdated($locationHiloId: String!){
    onAnyLocationUpdated(locationHiloId: $locationHiloId) {
        locationHiloId
        deviceType
        transmissionTime
        operationId
        location {
            ...on Container {
                hiloId
                devices {
                    deviceType
                    hiloId
                    physicalAddress
                    connectionStatus
                        ... on BasicChargeController {
                            connectionStatus
                        }
                        ... on LowVoltageThermostat {
                            connectionStatus
                        }
                }
            }
        }
    }
}"""

    async def call_get_location_query(self, location_hilo_id: str) -> None:
        """This functions calls the digital-twin and requests location id"""
        access_token = await self._get_access_token()
        url = f"https://{PLATFORM_HOST}/api/digital-twin/v3/graphql"
        headers = {"Authorization": f"Bearer {access_token}"}

        query = self.QUERY_GET_LOCATION
        query_hash = hashlib.sha256(query.encode("utf-8")).hexdigest()

        payload = {
            "extensions": {
                "persistedQuery": {
                    "version": 1,
                    "sha256Hash": query_hash,
                }
            },
            "variables": {"locationHiloId": location_hilo_id},
        }

        async with httpx.AsyncClient(http2=True) as client:
            try:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                response_json = response.json()
            except Exception as e:
                LOG.error("Error parsing response: %s", e)
                return

            if "errors" in response_json:
                for error in response_json["errors"]:
                    if error.get("message") == "PersistedQueryNotFound":
                        payload["query"] = query
                        try:
                            response = await client.post(
                                url, json=payload, headers=headers
                            )
                            response.raise_for_status()
                            response_json = response.json()
                        except Exception as e:
                            LOG.error("Error parsing response on retry: %s", e)
                            return
                        break

            if "errors" in response_json:
                LOG.error("GraphQL errors: %s", response_json["errors"])
                return

            if "data" in response_json:
                self._handle_query_result(response_json["data"])

    async def subscribe_to_device_updated(
        self, location_hilo_id: str, callback: callable = None
    ) -> None:
        LOG.debug("subscribe_to_device_updated called")
        await self._listen_to_sse(
            self.SUBSCRIPTION_DEVICE_UPDATED,
            {"locationHiloId": location_hilo_id},
            self._handle_device_subscription_result,
            callback,
            location_hilo_id,
        )

    async def subscribe_to_location_updated(
        self, location_hilo_id: str, callback: callable = None
    ) -> None:
        LOG.debug("subscribe_to_location_updated called")
        await self._listen_to_sse(
            self.SUBSCRIPTION_LOCATION_UPDATED,
            {"locationHiloId": location_hilo_id},
            self._handle_location_subscription_result,
            callback,
            location_hilo_id,
        )

    async def _listen_to_sse(
        self,
        query: str,
        variables: Dict[str, Any],
        handler: Callable[[Dict[str, Any]], str],
        callback: Optional[Callable[[str], None]] = None,
        location_hilo_id: str = None,
    ) -> None:
        query_hash = hashlib.sha256(query.encode("utf-8")).hexdigest()
        payload = {
            "extensions": {
                "persistedQuery": {
                    "version": 1,
                    "sha256Hash": query_hash,
                }
            },
            "variables": variables,
        }

        while True:
            try:
                access_token = await self._get_access_token()
                url = f"https://{PLATFORM_HOST}/api/digital-twin/v3/graphql"
                headers = {"Authorization": f"Bearer {access_token}"}

                retry_with_full_query = False

                async with httpx.AsyncClient(http2=True, timeout=None) as client:
                    async with aconnect_sse(
                        client, "POST", url, json=payload, headers=headers
                    ) as event_source:
                        async for sse in event_source.aiter_sse():
                            if not sse.data:
                                continue
                            try:
                                data = json.loads(sse.data)
                            except json.JSONDecodeError:
                                continue

                            if "errors" in data:
                                if any(
                                    e.get("message") == "PersistedQueryNotFound"
                                    for e in data["errors"]
                                ):
                                    retry_with_full_query = True
                                    break
                                LOG.error(
                                    "GraphQL Subscription Errors: %s", data["errors"]
                                )
                                continue

                            if "data" in data:
                                LOG.debug(
                                    "Received subscription result %s", data["data"]
                                )
                                result = handler(data["data"])
                                if callback:
                                    callback(result)

                if retry_with_full_query:
                    payload["query"] = query
                    continue

            except Exception as e:
                LOG.debug(
                    "Subscription connection lost: %s. Reconnecting in 5 seconds...", e
                )
                await asyncio.sleep(5)
                # Reset payload to APQ only on reconnect
                if "query" in payload:
                    del payload["query"]

                if location_hilo_id:
                    try:
                        await self.call_get_location_query(location_hilo_id)
                        LOG.debug("call_get_location_query success after reconnect")
                    except Exception as e2:
                        LOG.error(
                            "exception while RE-connecting, retrying: %s",
                            e2,
                        )

    async def _get_access_token(self) -> str:
        """Get the access token."""
        return await self._api.async_get_access_token()

    def _handle_query_result(self, result: Dict[str, Any]) -> None:
        """This receives query results and maps them to the proper device."""
        devices_values: list[any] = result["getLocation"]["devices"]
        attributes = self.mapper.map_query_values(devices_values)
        self._devices.parse_values_received(attributes)

    def _handle_device_subscription_result(self, result: Dict[str, Any]) -> str:
        devices_values: list[any] = result["onAnyDeviceUpdated"]["device"]
        attributes = self.mapper.map_device_subscription_values(devices_values)
        updated_device = self._devices.parse_values_received(attributes)
        # callback to update the device in the UI
        LOG.debug("Device updated: %s", updated_device)
        return devices_values.get("hiloId")

    def _handle_location_subscription_result(self, result: Dict[str, Any]) -> str:
        devices_values: list[any] = result["onAnyLocationUpdated"]["location"]
        attributes = self.mapper.map_location_subscription_values(devices_values)
        updated_device = self._devices.parse_values_received(attributes)
        # callback to update the device in the UI
        LOG.debug("Device updated: %s", updated_device)
        return devices_values.get("hiloId")
