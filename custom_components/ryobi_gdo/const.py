"""Constants for ryobi_gdo."""

from homeassistant.const import Platform

NAME = "Ryobi GDO"
DOMAIN = "ryobi_gdo"
VERSION = "0.9.4"
ATTRIBUTION = "Data provided by Ryobi"
ISSUE_URL = "https://github.com/catduckgnaf/ryobi_gdo/issues"

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.CAMERA,
    Platform.COVER,
    Platform.FAN,
    Platform.SENSOR,
    Platform.SWITCH,
]

HOST_URI = "tti.tiwiconnect.com"
DEFAULT_HOST = "tti.tiwiconnect.com"
LOGIN_ENDPOINT = "api/login"
DEVICE_GET_ENDPOINT = "api/devices"
DEVICE_SET_ENDPOINT = "api/wsrpc"
REQUEST_TIMEOUT = 30

ATTR_ATTRIBUTION = "attribution"

# Configuration constants
CONF_DEVICE_ID = "device_id"
CONF_HOST = "host"

# WSS Messages
GARAGE_UPDATE_MSG = "wskAttributeUpdateNtfy"
WS_AUTH_OK = "authorizedWebSocket"
WS_OK = "OK"

# Socket
SOCK_CONNECTED = "Open"
SOCK_CLOSE = "Close"
SOCK_ERROR = "Error"

# Time in seconds before websocket inactivity triggers reconnect
WS_INACTIVITY_TIMEOUT = 360

# Fan speed range as (min, max) raw module values. The wall keypad cycles
# Off -> High -> Medium -> Low, while the module stores an ordinal speed
# starting at 1.
FAN_SPEED_RANGE = (1, 3)
