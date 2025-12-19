import logging
import platform
from typing import Final

import aiohttp

LOG: Final = logging.getLogger(__package__)
DEFAULT_STATE_FILE: Final = "hilo_state.yaml"
REQUEST_RETRY: Final = 9
PYHILO_VERSION: Final = "2025.12.05"
# TODO: Find a way to keep previous line in sync with pyproject.toml automatically

CONTENT_TYPE_FORM: Final = "application/x-www-form-urlencoded"
ANDROID_PKG_NAME: Final = "com.hiloenergie.hilo"
DOMAIN: Final = "hilo"
# Auth constants
AUTH_HOSTNAME: Final = "connexion.hiloenergie.com"
AUTH_ENDPOINT: Final = "/HiloDirectoryB2C.onmicrosoft.com/B2C_1A_SIGN_IN/oauth2/v2.0/"
AUTH_AUTHORIZE: Final = f"https://{AUTH_HOSTNAME}{AUTH_ENDPOINT}authorize"
AUTH_TOKEN: Final = f"https://{AUTH_HOSTNAME}{AUTH_ENDPOINT}token"
AUTH_CHALLENGE_METHOD: Final = "S256"
AUTH_CLIENT_ID: Final = "1ca9f585-4a55-4085-8e30-9746a65fa561"
AUTH_SCOPE: Final = "openid https://HiloDirectoryB2C.onmicrosoft.com/hiloapis/user_impersonation offline_access"
SUBSCRIPTION_KEY: Final = "20eeaedcb86945afa3fe792cea89b8bf"

# API constants
API_HOSTNAME: Final = "api.hiloenergie.com"
API_END: Final = "v1/api"
API_AUTOMATION_ENDPOINT: Final = f"/Automation/{API_END}"
API_CHALLENGE_ENDPOINT: Final = f"/challenge/{API_END}"
API_GD_SERVICE_ENDPOINT: Final = f"/GDService/{API_END}"
API_NOTIFICATIONS_ENDPOINT: Final = "/Notifications"
API_EVENTS_ENDPOINT: Final = "/Notifications"
API_REGISTRATION_ENDPOINT: Final = f"{API_NOTIFICATIONS_ENDPOINT}/Registrations"
PLATFORM_HOST: Final = "platform.hiloenergie.com"

API_REGISTRATION_HEADERS: Final = {
    "AppId": ANDROID_PKG_NAME,
    "Provider": "fcm",
    "Hilo-Tenant": DOMAIN,
}

# Automation server constant
AUTOMATION_DEVICEHUB_ENDPOINT: Final = "/DeviceHub"
AUTOMATION_CHALLENGE_ENDPOINT: Final = "/ChallengeHub"


# Request constants
DEFAULT_USER_AGENT: Final = f"PyHilo/{PYHILO_VERSION} aiohttp/{aiohttp.__version__} Python/{platform.python_version()}"


# NOTE(dvd): Not sure how to get new ones so I'm using the ones from my emulator
# We can't unfortunately randomize this device id, I believe it's generated when
# an android device registers to the play store, but I'm no android dev.
# ANDROID_DEVICE_ID: Final = 3530136576518667218
# NOTE(dvd): Based on issue #113, this can be set to 0
ANDROID_DEVICE_ID: Final = 3530136576518667218

ANDROID_DEVICE_SECURITY_TOKEN: Final = 7776414007788361535
ANDROID_CERT: Final = "59F0B6042655AD8AE46120E42417F80641D14CEF"
GOOGLE_API_KEY: Final = "AIzaSyAHZ8_vQRoZZshDkQ0gsPVxSJ_RWQynMWQ"
ANDROID_SENDER: Final = 18450192328

# Firebase stuff
FB_INSTALL_HOSTNAME: Final = "firebaseinstallations.googleapis.com"
FB_INSTALL_ENDPOINT: Final = "/v1/projects/hilo-eeca5/installations"

FB_CLIENT: Final = (
    "android-target-sdk/30 android-min-sdk/24 android-installer/ fire-core/19.5.0 fire-iid/21.0.1 "
    "fire-android/30 device-model/generic_x86 device-brand/Android android-platform/ fire-fcm/20.1.7_1p "
    "device-name/sdk_phone_x86 fire-installations/16.3.5"
)

FB_INSTALL_HEADERS: Final = {
    "Cache-Control": "no-cache",
    "X-Android-Package": ANDROID_PKG_NAME,
    "x-firebase-client": FB_CLIENT,
    "x-firebase-client-log-type": "3",
    "X-Android-Cert": ANDROID_CERT,
    "x-goog-api-key": GOOGLE_API_KEY,
    "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 11; Android SDK built for x86 Build/RSR1.210210.001.A1)",
}

FB_ID_LEN: Final = 22
FB_AUTH_VERSION: Final = "FIS_v2"
FB_SDK_VERSION: Final = "a:16.3.5"
FB_APP_ID: Final = f"1:{ANDROID_SENDER}:android:4f13f4d0bc62544c63d2fd"

ANDROID_CLIENT_HOSTNAME: Final = "android.clients.google.com"
ANDROID_CLIENT_ENDPOINT: Final = "/c2dm/register3"
ANDROID_GCM_VERSION: Final = "201817022"
ANDROID_DEVICE_ID_LEN: Final = 19

ANDROID_CLIENT_HEADERS: Final = {
    "Authorization": f"AidLogin {ANDROID_DEVICE_ID}:{ANDROID_DEVICE_SECURITY_TOKEN}",
    "app": ANDROID_PKG_NAME,
    "gcm_ver": ANDROID_GCM_VERSION,
    "User-Agent": "Android-GCM/1.5 (generic_x86 RSR1.210210.001.A1)",
    "content-type": CONTENT_TYPE_FORM,
}


ANDROID_CLIENT_POST: Final = {
    # 'X-appid': # This is the FID
    # 'X-Goog-Firebase-Installations-Auth': # This is the token from the FID
    "device": ANDROID_DEVICE_ID,
    "X-subtype": ANDROID_SENDER,
    "sender": ANDROID_SENDER,
    "X-app_ver": 5357,
    "X-osv": 30,
    "X-cliv": "fiid-21.0.1",
    "X-gmsv": ANDROID_GCM_VERSION,
    "X-scope": "*",
    "X-gmp_app_id": FB_APP_ID,
    "X-firebase-app-name-hash": "R1dAH9Ui7M-ynoznwBdw01tLxhI",
    "X-Firebase-Client": FB_CLIENT,
    "X-Firebase-Client-Log-Type": 1,
    "X-app_ver_name": PYHILO_VERSION,
    "app": ANDROID_PKG_NAME,
    "app_ver": 5357,
    "info": "Y8qNKupTk7IVoLPgN7e-uDAzqVicyRc",
    "gcm_ver": ANDROID_GCM_VERSION,
    "plat": 0,
    "cert": ANDROID_CERT.lower(),
    "target_ver": 30,
}

HILO_DEVICE_ATTRIBUTES: Final = [
    "asset_id",
    "category",
    "disconnected",
    "external_group",
    "firmware_version",
    "gateway_external_id",
    "gateway_id",
    "group_id",
    "heating",
    "hilo_id",
    "humidity",
    "icon",
    "id",
    "identifier",
    "is_favorite",
    "last_status_time",
    "last_update",
    "load_connected",
    "location_id",
    "model_number",
    "name",
    "online_status",
    "parameters",
    "power",
    "provider",
    "provider_data",
    "sdi",
    "settable_attributes",
    "settable_attributes_list",
    "supported_attributes",
    "supported_attributes_list",
    "supported_parameters",
    "supported_parameters_list",
    "sw_version",
    "type",
    "unpaired",
    "zig_bee_channel",
    "zigbee_channel",
    "zig_bee_pairing_activated",
    "gateway_asset_id",
    "e_tag",
]

HILO_LIST_ATTRIBUTES: Final = [
    "settable_attributes",
    "supported_attributes",
    "supported_parameters",
]

HILO_DEVICE_TYPES: Final = {
    "ChargingPoint": "Sensor",
    "ColorBulb": "Light",
    "WhiteBulb": "Light",
    "Gateway": "Sensor",
    "IndoorWeatherStation": "Sensor",
    "LightDimmer": "Light",
    "LightSwitch": "Light",
    "Meter": "Sensor",
    "OutdoorWeatherStation": "Sensor",
    "Outlet": "Switch",
    "SmokeDetector": "Sensor",
    "Thermostat": "Climate",
    "FloorThermostat": "Climate",
    "Ccr": "Switch",
    "Cee": "Switch",
    "Thermostat24V": "Climate",
    "Tracker": "Sensor",
}

HILO_UNIT_CONVERSION: Final = {
    "Celsius": "°C",
    "DB": "dB",
    "Integer": "dB",
    "Mbar": "mbar",
    "Percentage": "%",
    "PPM": "ppm",
    "Watt": "W",
}

HILO_READING_TYPES: Final = {
    "BatteryPercent": "Percentage",
    "Co2": "PPM",
    "ColorTemperature": "Integer",
    "CurrentTemperature": "Celsius",
    "Disconnected": "null",
    "DrmsState": "OnOff",
    "firmwareVersion": "null",
    "Heating": "Percentage",
    "Hue": "Integer",
    "Humidity": "Percentage",
    "Intensity": "Percentage",
    "MaxTempSetpoint": "Celsius",
    "MinTempSetpoint": "Celsius",
    "Noise": "DB",
    "onlineStatus": "null",
    "OnOff": "OnOff",
    "Power": "Watt",
    "Pressure": "Mbar",
    "Saturation": "Integer",
    "Status": "OnOff",
    "TargetTemperature": "Celsius",
    "Unpaired": "null",
    "WifiStatus": "Integer",
    "zigBeePairingActivated": "OnOff",
    "zigBeeChannel": "Integer",
}

HILO_PROVIDERS: Final = {
    0: "Hass-Hilo",
    1: "Hilo",
    2: "Netatmo",
    3: "OneLink",
}

JASCO_MODELS: Final = [
    "43080",
    "43082",
    "43076",
    "43078",
    "43100",
    "46199",
    "9063",
    "45678",
    "42405",
    "43094",
    "43095",
    "45853",
]

JASCO_OUTLETS: Final = [
    "42405",
    "43094",
    "43095",
    "43100",
    "45853",
]

UNMONITORED_DEVICES: Final = [
    "43076",
    "43080",
    "43094",
    "43100",
]

STATE_UNKNOWN: Final = "unknown"
