import asyncio
from typing import Any, Dict, List, Optional

from gql import Client, gql
from gql.transport.aiohttp import AIOHTTPTransport
from gql.transport.websockets import WebsocketsTransport

from pyhilo import API
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
        access_token = await self._get_access_token()
        transport = AIOHTTPTransport(
            url="https://platform.hiloenergie.com/api/digital-twin/v3/graphql",
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
        while True:  # Loop to reconnect if the connection is lost
            access_token = await self._get_access_token()
            transport = WebsocketsTransport(
                url=f"wss://platform.hiloenergie.com/api/digital-twin/v3/graphql?access_token={access_token}"
            )
            client = Client(transport=transport, fetch_schema_from_transport=True)
            query = gql(self.SUBSCRIPTION_DEVICE_UPDATED)
            try:
                async with client as session:
                    async for result in session.subscribe(
                        query, variable_values={"locationHiloId": location_hilo_id}
                    ):
                        print(f"Received subscription result {result}")
                        device_hilo_id = self._handle_device_subscription_result(result)
                        if callback:
                            callback(device_hilo_id)
            except Exception as e:
                print(f"Connection lost: {e}. Reconnecting in 5 seconds...")
                await asyncio.sleep(5)
                self.call_get_location_query(location_hilo_id)

    async def subscribe_to_location_updated(
        self, location_hilo_id: str, callback: callable = None
    ) -> None:
        access_token = await self._get_access_token()
        transport = WebsocketsTransport(
            url=f"wss://platform.hiloenergie.com/api/digital-twin/v3/graphql?access_token={access_token}"
        )
        client = Client(transport=transport, fetch_schema_from_transport=True)
        query = gql(self.SUBSCRIPTION_LOCATION_UPDATED)
        try:
            async with client as session:
                async for result in session.subscribe(
                    query, variable_values={"locationHiloId": location_hilo_id}
                ):
                    print(f"Received subscription result {result}")
                    device_hilo_id = self._handle_location_subscription_result(result)
                    callback(device_hilo_id)
        except asyncio.CancelledError:
            print("Subscription cancelled.")
            asyncio.sleep(1)
            await self.subscribe_to_location_updated(location_hilo_id)

    async def _get_access_token(self) -> str:
        """Get the access token."""
        return await self._api.async_get_access_token()

    def _handle_query_result(self, result: Dict[str, Any]) -> None:
        devices_values: list[any] = result["getLocation"]["devices"]
        attributes = self.mapper.map_query_values(devices_values)
        self._devices.parse_values_received(attributes)

    def _handle_device_subscription_result(self, result: Dict[str, Any]) -> str:
        devices_values: list[any] = result["onAnyDeviceUpdated"]["device"]
        attributes = self.mapper.map_device_subscription_values(devices_values)
        updated_device = self._devices.parse_values_received(attributes)
        # callback to update the device in the UI
        print(f"Device updated: {updated_device}")
        return devices_values.get("hiloId")

    def _handle_location_subscription_result(self, result: Dict[str, Any]) -> str:
        devices_values: list[any] = result["onAnyLocationUpdated"]["location"]
        attributes = self.mapper.map_location_subscription_values(devices_values)
        updated_device = self._devices.parse_values_received(attributes)
        # callback to update the device in the UI
        print(f"Device updated: {updated_device}")
        return devices_values.get("hiloId")
