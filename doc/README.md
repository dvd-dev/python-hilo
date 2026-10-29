# Hilo API reference payloads

Captured responses from Hilo's services, grouped by transport to mirror the library modules.
IDs, URNs and serial numbers in the payload files are anonymized.

| Folder | Transport | Library module | Contents |
|---|---|---|---|
| [`rest/`](rest/) | HTTPS REST | `pyhilo/api.py` | Automation (`/Locations`, `/Weather`) and challenge season endpoints |
| [`graphql/`](graphql/) | GraphQL subscription | `pyhilo/graphql.py` | `onAnyDeviceUpdated` payloads per device type |
| [`signalr/devicehub/`](signalr/devicehub/) | SignalR WebSocket | `pyhilo/signalr.py` | DeviceHub messages |
| [`signalr/challengehub/`](signalr/challengehub/) | SignalR WebSocket | `pyhilo/signalr.py` | ChallengeHub messages, 2025-26 season onward (CH = Winter Credits, Flex = Flex D) |
| [`signalr/challengehub/legacy-pre-2025/`](signalr/challengehub/legacy-pre-2025/) | SignalR WebSocket | — | Challenge messages before the CH/Flex split; kept for reference |
| [`postman/`](postman/) | — | — | Postman collection and environment for manual testing |

## Adding a payload

1. Strip tokens, location URNs, serial numbers and personal data before committing.
2. Name REST files after the endpoint (`season_events_ch_2025.json`) and SignalR/GraphQL files after the message target (`EventCHDetailsInitialValuesReceived.json`).
3. Add a short suffix for variants (`-during-event`, `-empty`, `-meter`).

# Using Postman to query Hilo

Import [`postman/hilo.postman_collection.json`](postman/hilo.postman_collection.json) and [`postman/hilo-prod.postman_environment.json`](postman/hilo-prod.postman_environment.json), then select the **Hilo Prod** environment.

## Authentication

The collection uses OAuth 2.0 at the collection level. Open the collection's **Authorization** tab, click **Get New Access Token**, log in with your Hilo credentials in the browser window, then click **Use Token**. Every request in the collection inherits that token.

Tokens are short-lived and contain personally identifiable information. Do not share them or commit an exported environment that contains them.

## REST requests

With the access token set, the REST requests (`1-Get Locations`, `Get SeasonsSummary`, `Get CHEvents`, `Get FlexEvents`, ...) can be sent directly.

## Connecting to a hub

Each hub folder (`DeviceHub`, `ChallengeHub`) contains two negotiate requests. Send them in order:

1. `1-API Hilo ... Hub Negotiate` stores the hub URL and hub access token in the environment (`_deviceHubUrl` / `_deviceHubAccessToken`, or `_challengeHubUrl` / `_challengeHubAccessToken`).
2. `2-... Hub Negotiate` stores the connection token (`_deviceHubConnectionToken` or `_challengeHubConnectionToken`).

Then open a new WebSocket request in Postman:

1. Use the hub URL from the environment (`{{_deviceHubUrl}}` or `{{_challengeHubUrl}}`).
2. In **Headers**, add `Authorization` with the value `Bearer {{_deviceHubAccessToken}}` (or `Bearer {{_challengeHubAccessToken}}`).
3. Connect, then send the handshake below. The trailing record separator character `chr(30)` is required after every message.

```
{
    "protocol": "json",
    "version": 1
}
```

### DeviceHub

Invoke `SubscribeToLocation` with your location ID to get your device information:

```
{
    "arguments": [
        69420
    ],
    "invocationId": "0",
    "target": "SubscribeToLocation",
    "type": 1
}
```

You should receive a [`DeviceListInitialValuesReceived`](signalr/devicehub/DeviceListInitialValuesReceived.json) message back.

### ChallengeHub

Since the 2025-2026 season and the addition of Flex D, messages are split between Winter Credits (Crédit Hivernal) and Flex D. Winter Credits targets contain `CH` and Flex D targets contain `Flex`. Each rate has its own event ID; for example, event 337 was for Winter Credits and event 338 for Flex D, both at the same time. You only have access to the one matching your rate.

#### SubscribeToEventCH or SubscribeToEventFlex

```
{
    "arguments": [
        {
            "locationHiloId": "urn:YOUR-URN",
            "eventId": ID(numeric)
        }
    ],
    "invocationId": "1",
    "target": "SubscribeToEventCH",
    "type": 1
}
```

Returns [`EventCHDetailsInitialValuesReceived`](signalr/challengehub/EventCHDetailsInitialValuesReceived.json) or [`EventFlexDetailsInitialValuesReceived`](signalr/challengehub/EventFlexDetailsInitialValuesReceived.json).
