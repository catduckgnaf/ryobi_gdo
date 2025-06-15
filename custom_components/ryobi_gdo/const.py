"""Constants for ryobi_gdo."""

NAME = "Ryobi GDO"
DOMAIN = "ryobi_gdo"
VERSION = "0.4.0"
ATTRIBUTION = "Data provided by Ryobi"
ISSUE_URL = "https://github.com/catduckgnaf/ryobi_gdo/issues"

PLATFORMS = ["binary_sensor", "cover", "sensor", "switch"]

HOST_URI = "tti.tiwiconnect.com"
LOGIN_ENDPOINT = "api/login"
DEVICE_GET_ENDPOINT = "api/devices"
DEVICE_SET_ENDPOINT = "api/wsrpc"
REQUEST_TIMEOUT = 3
COORDINATOR = "coordinator"

ATTR_ATTRIBUTION = "attribution"

# Configuration constants
CONF_DEVICE_ID = "device_id"

# Device Model
# deviceTypeIds = "gdoMasterUnit" or # "GD125"


# WSS Messages
GARAGE_UPDATE_MSG = "wskAttributeUpdateNtfy"
WS_AUTH_OK = "authorizedWebSocket"
WS_CMD_ACK = "result"
WS_OK = "OK"

# Socket
SOCK_CONNECTED = "Open"
SOCK_CLOSE = "Close"
SOCK_ERROR = "Error"

# Time in seconds before websocket inactivity triggers reconnect
WS_INACTIVITY_TIMEOUT = 360
