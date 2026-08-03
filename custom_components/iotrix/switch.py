"""D18 guard behavior switches."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import IoTrixRuntimeData
from .entity import GuardEntity


class GuardSwitch(GuardEntity, SwitchEntity):
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, entry_id: str, guard: Any, key: str, name: str, icon: str) -> None:
        super().__init__(entry_id, guard, key)
        self.key = key
        self._attr_name = name
        self._attr_icon = icon

    @property
    def is_on(self) -> bool:
        return bool(self.guard.params[self.key])

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.guard.async_set_param(self.key, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.guard.async_set_param(self.key, False)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    runtime: IoTrixRuntimeData = entry.runtime_data
    async_add_entities(
        [
            GuardSwitch(
                entry.entry_id,
                runtime.guard,
                "enabled",
                "Protection Enabled",
                "mdi:shield-lock",
            ),
            GuardSwitch(
                entry.entry_id,
                runtime.guard,
                "auto_restore",
                "Automatic Restore",
                "mdi:restore",
            ),
            GuardSwitch(
                entry.entry_id,
                runtime.guard,
                "emergency_rollback",
                "Emergency Rollback",
                "mdi:shield-refresh",
            ),
        ]
    )
