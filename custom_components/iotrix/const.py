"""Constants for the IoTrix Cloud integration."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "iotrix"
NAME = "IoTrix Cloud"

CONF_HOST = "host"
CONF_TOKEN = "token"
CONF_DEVICE_REFRESH_INTERVAL = "device_refresh_interval"
CONF_GUARD_HYBRID_ID = "guard_hybrid_id"
CONF_GUARD_BMS_ID = "guard_bms_id"

DEFAULT_DEVICE_REFRESH_INTERVAL = 300
DEFAULT_WS_INTERVAL = 1

PLATFORMS = (
    "binary_sensor",
    "event",
    "number",
    "sensor",
    "switch",
)

GUARD_DEVICE_SUFFIX = "d18_guard"
GUARD_EVALUATION_INTERVAL = timedelta(seconds=1)
GUARD_BMS_FRESH_SECONDS = 45.0
GUARD_TELEMETRY_FRESH_SECONDS = 60.0

D18_DRIVER = "mppt_makeskyblue_v1"
D18_FIELD = "max_on_grid_current"
D18_COMMAND = "ctrl_max_on_grid_current"
D18_MIN = 0.0
D18_MAX = 31.8

EVENT_TYPE = f"{DOMAIN}_d18_guard_event"

GUARD_DEFAULTS: dict[str, float | bool] = {
    "enabled": False,
    "auto_restore": True,
    "emergency_rollback": True,
    "trigger_current": 50.0,
    "target_current": 45.0,
    "release_current": 42.0,
    "restore_target": 30.0,
    "minimum_d18": 5.0,
    "conversion_efficiency": 90.0,
    "pv_headroom": 0.5,
    "reduction_margin": 0.5,
    "minimum_controllable_power": 200.0,
    "recovery_headroom": 1.0,
    "trip_delay": 30.0,
    "minimum_write_interval": 600.0,
    "recovery_observation": 600.0,
    "restore_verification": 600.0,
    "recovery_lock": 1800.0,
}
