class GraphQlHelper:
    def query_get_location() -> str:
        return """query getLocation($locationHiloId: String!) {
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
                            power {
                                value
                                kind
                            }
                        }
                    }
                }
            }"""
