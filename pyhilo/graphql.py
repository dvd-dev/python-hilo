import asyncio
import logging
import ssl
from typing import Any, Dict, List, Optional

from gql import Client, gql
from gql.transport.aiohttp import AIOHTTPTransport
from gql.transport.websockets import WebsocketsTransport

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
        transport = AIOHTTPTransport(
            url=f"https://{PLATFORM_HOST}/api/digital-twin/v3/graphql",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        client = Client(transport=transport, fetch_schema_from_transport=True)
        query = gql(self.QUERY_GET_LOCATION)

        async with client as session:
            result = await session.execute(
                query, variable_values={"locationHiloId": location_hilo_id}
            )
        self._handle_query_result(result)

    async def subscribe_to_device_updated(
        self, location_hilo_id: str, callback: callable = None
    ) -> None:
        LOG.debug("subscribe_to_device_updated called")

        # Setting log level to suppress keepalive messages on gql transport
        logging.getLogger("gql.transport.websockets").setLevel(logging.WARNING)

        #
        loop = asyncio.get_event_loop()
        ssl_context = await loop.run_in_executor(None, ssl.create_default_context)

        while True:  # Loop to reconnect if the connection is lost
            LOG.debug("subscribe_to_device_updated while true")
            access_token = await self._get_access_token()
            transport = WebsocketsTransport(
                url=f"wss://{PLATFORM_HOST}/api/digital-twin/v3/graphql?access_token={access_token}",
                ssl=ssl_context,
            )
            client = Client(transport=transport, fetch_schema_from_transport=True)
            query = gql(self.SUBSCRIPTION_DEVICE_UPDATED)
            try:
                async with client as session:
                    async for result in session.subscribe(
                        query, variable_values={"locationHiloId": location_hilo_id}
                    ):
                        LOG.debug(
                            "subscribe_to_device_updated: Received subscription result %s",
                            result,
                        )
                        device_hilo_id = self._handle_device_subscription_result(result)
                        if callback:
                            callback(device_hilo_id)
            except Exception as e:
                LOG.debug(
                    "subscribe_to_device_updated: Connection lost: %s. Reconnecting in 5 seconds...",
                    e,
                )
                await asyncio.sleep(5)
                try:
                    await self.call_get_location_query(location_hilo_id)
                    LOG.debug(
                        "subscribe_to_device_updated, call_get_location_query success"
                    )

                except Exception as e2:
                    LOG.error(
                        "subscribe_to_device_updated, exception while reconnecting, retrying: %s",
                        e2,
                    )

    async def subscribe_to_location_updated(
        self, location_hilo_id: str, callback: callable = None
    ) -> None:
        access_token = await self._get_access_token()
        transport = WebsocketsTransport(
            url=f"wss://{PLATFORM_HOST}/api/digital-twin/v3/graphql?access_token={access_token}"
        )
        client = Client(transport=transport, fetch_schema_from_transport=True)
        query = gql(self.SUBSCRIPTION_LOCATION_UPDATED)
        try:
            async with client as session:
                async for result in session.subscribe(
                    query, variable_values={"locationHiloId": location_hilo_id}
                ):
                    LOG.debug("Received subscription result %s", result)
                    device_hilo_id = self._handle_location_subscription_result(result)
                    callback(device_hilo_id)
        except asyncio.CancelledError:
            LOG.debug("Subscription cancelled.")
            asyncio.sleep(1)
            await self.subscribe_to_location_updated(location_hilo_id)

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
