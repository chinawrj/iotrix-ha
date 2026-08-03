"""D18 guard event entity for HA automations and audit history."""

from __future__ import annotations

from typing import Any

from homeassistant.components.event import EventEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import IoTrixRuntimeData
from .entity import GuardEntity
from .guard import GuardEvent

EVENT_TYPES = [
    "boot_snapshot",
    "guard_enabled",
    "guard_disabled",
    "trip_started",
    "blocked_uncontrollable",
    "limit_requested",
    "limit_accepted",
    "limit_confirmed",
    "limit_failed",
    "recovery_started",
    "restore_requested",
    "restore_accepted",
    "restore_confirmed",
    "restore_failed",
    "restore_verified",
    "rollback_requested",
    "rollback_accepted",
    "rollback_confirmed",
    "rollback_failed",
    "recovery_lock_expired",
    "manual_confirmed",
]


class D18GuardEventEntity(GuardEntity, EventEntity):
    _attr_name = "Event"
    _attr_event_types = EVENT_TYPES

    def __init__(self, entry_id: str, guard: Any) -> None:
        super().__init__(entry_id, guard, "event")
        self._remove_event_listener: Any = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._remove_event_listener = self.guard.add_event_listener(self._handle_event)

    async def async_will_remove_from_hass(self) -> None:
        if self._remove_event_listener is not None:
            self._remove_event_listener()
        await super().async_will_remove_from_hass()

    @callback
    def _handle_event(self, event: GuardEvent) -> None:
        self._trigger_event(
            event.event_type,
            {"sequence": event.sequence, "timestamp": event.timestamp, **event.details},
        )
        self.async_write_ha_state()


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    runtime: IoTrixRuntimeData = entry.runtime_data
    async_add_entities([D18GuardEventEntity(entry.entry_id, runtime.guard)])
