"""Constants for the IoTrix Cloud integration."""

from __future__ import annotations

DOMAIN = "iotrix"
NAME = "IoTrix Cloud"

CONF_HOST = "host"
CONF_TOKEN = "token"
CONF_DEVICE_REFRESH_INTERVAL = "device_refresh_interval"
DEFAULT_HOST = "https://api.ea-1.iotrix.net"
DEFAULT_DEVICE_REFRESH_INTERVAL = 300
DEFAULT_WS_INTERVAL = 1

PLATFORMS = (
    "binary_sensor",
    "number",
    "sensor",
)

D18_DRIVER = "mppt_makeskyblue_v1"
D18_FIELD = "max_on_grid_current"
D18_COMMAND = "ctrl_max_on_grid_current"
D18_MIN = 0.0
D18_MAX = 31.8
