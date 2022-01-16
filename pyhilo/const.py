import logging
from typing import Final

LOG: Final = logging.getLogger(__package__)
DEFAULT_STATE_FILE: Final = "hilo_state.yaml"
REQUEST_RETRY: Final = 2
TIMEOUT: Final = 10
TOKEN_EXPIRATION_PADDING: Final = 300
VERIFY: Final = True
DEVICE_REFRESH_TIME: Final = 1800
HILO_APP_VERSION: Final = "3.0.212"

CONTENT_TYPE_FORM: Final = "application/x-www-form-urlencoded"
ANDROID_PKG_NAME: Final = "com.hiloenergie.hilo"
DOMAIN: Final = "hilo"
# Auth constants
AUTH_HOSTNAME: Final = "hilodirectoryb2c.b2clogin.com"
AUTH_ENDPOINT: Final = (
    "/hilodirectoryb2c.onmicrosoft.com/oauth2/v2.0/token?p=B2C_1A_B2C_1_PasswordFlow"
)
AUTH_CLIENT_ID: Final = "9870f087-25f8-43b6-9cad-d4b74ce512e1"
AUTH_TYPE_PASSWORD: Final = "password"
AUTH_TYPE_REFRESH: Final = "refresh_token"
AUTH_RESPONSE_TYPE: Final = "token id_token"
AUTH_SCOPE: Final = "openid 9870f087-25f8-43b6-9cad-d4b74ce512e1 offline_access"
SUBSCRIPTION_KEY: Final = "20eeaedcb86945afa3fe792cea89b8bf"

# API constants
API_HOSTNAME: Final = "apim.hiloenergie.com"
API_END: Final = "v1/api"
API_AUTOMATION_ENDPOINT: Final = f"/Automation/{API_END}"
API_GD_SERVICE_ENDPOINT: Final = f"/GDService/{API_END}"
API_NOTIFICATIONS_ENDPOINT: Final = "/Notifications"
API_EVENTS_ENDPOINT: Final = "/Events"
API_REGISTRATION_ENDPOINT: Final = f"{API_NOTIFICATIONS_ENDPOINT}/Registrations"

API_REGISTRATION_HEADERS: Final = {
    "AppId": ANDROID_PKG_NAME,
    "Provider": "fcm",
    "Hilo-Tenant": DOMAIN,
}

# Automation server constants
AUTOMATION_HOSTNAME: Final = "automation.hiloenergie.com"
AUTOMATION_DEVICEHUB_ENDPOINT: Final = "/DeviceHub"

# Request constants
DEFAULT_USER_AGENT: Final = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Safari/605.1.15"
)


# NOTE(dvd): Not sure how to get new ones so I'm using the ones from my emulator
# We can't unfortunately randomize this device id, I believe it's generated when
# an android device registers to the play store, but I'm no android dev.
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
    "X-app_ver_name": HILO_APP_VERSION,
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
    "icon",
    "id",
    "identifier",
    "load_connected",
    "location_id",
    "model_number",
    "name",
    "online_status",
    "parameters",
    "provider",
    "provider_data",
    "settable_attributes",
    "supported_attributes",
    "supported_parameters",
    "sw_version",
    "type",
    "zig_bee_channel",
    "zig_bee_pairing_activated",
]

HILO_LIST_ATTRIBUTES: Final = [
    "settable_attributes",
    "supported_attributes",
    "supported_parameters",
]

HILO_DEVICE_TYPES: Final = {
    "ChargingPoint": "Sensor",
    "Gateway": "Sensor",
    "IndoorWeatherStation": "Sensor",
    "LightDimmer": "Light",
    "LightSwitch": "Light",
    "Meter": "Sensor",
    "OutdoorWeatherStation": "Sensor",
    "SmokeDetector": "Sensor",
    "Thermostat": "Climate",
    "Tracker": "Sensor",
}

HILO_UNIT_CONVERSION: Final = {
    "Celcius": "°C",
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
    "CurrentTemperature": "Celcius",
    "Disconnected": "null",
    "DrmsState": "OnOff",
    "Heating": "Percentage",
    "Humidity": "Percentage",
    "Intensity": "Percentage",
    "MaxTempSetpoint": "Celcius",
    "MinTempSetpoint": "Celcius",
    "Noise": "DB",
    "OnOff": "OnOff",
    "Power": "Watt",
    "Pressure": "Mbar",
    "TargetTemperature": "Celcius",
    "WifiStatus": "Integer",
}

HILO_PROVIDERS: Final = {
    0: "Hass-Hilo",
    1: "Hilo",
    2: "Netatmo",
    3: "OneLink",
}
