"""Constants for ryobi_gdo."""
import logging

NAME = "Ryobi GDO"
DOMAIN = "ryobi_gdo"
VERSION = "0.1.0"
ATTRIBUTION = "Data provided by Ryobi"
ISSUE_URL = "https://github.com/catduckgnaf/ryobi_gdo/issues"

LOGGER = logging.getLogger(__name__)
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
