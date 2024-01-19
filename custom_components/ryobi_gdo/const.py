"""Constants for ryobi_gdo."""

NAME = "Ryobi GDO"
DOMAIN = "ryobi_gdo"
VERSION = "0.1.1"
ATTRIBUTION = "Data provided by Ryobi"
ISSUE_URL = "https://github.com/catduckgnaf/ryobi_gdo/issues"

PLATFORMS = ["cover", "switch", "sensor", "binary_sensor"]

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

# GDO125

# GDO200

# WSS Messages
GARAGE_UPDATE_MSG = "wskAttributeUpdateNtfy"
WS_AUTH_OK = "authorizedWebSocket"
WS_CMD_ACK = "result"
WS_OK = "OK"

# Socket
SOCK_CONNECTED = "Open"
SOCK_CLOSE = "Close"
SOCK_ERROR = "Error"
