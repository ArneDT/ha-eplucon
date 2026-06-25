from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable

from dacite import from_dict
from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, normalize_bool
from .eplucon_api.DTO.DeviceDTO import DeviceDTO
from .eplucon_api.eplucon_portal_client import EpluconPortalClient, PortalAuthError, PortalError

_LOGGER = logging.getLogger(__name__)


@dataclass(kw_only=True)
class EpluconSwitchDescription(SwitchEntityDescription):
    command: str
    read_fn: Callable[[DeviceDTO], bool | None] = field(default=lambda _: None)


SWITCH_DESCRIPTIONS: list[EpluconSwitchDescription] = [
    EpluconSwitchDescription(
        key="heating_active",
        name="Heating Active",
        command="heating_active",
        read_fn=lambda d: (
            normalize_bool(d.realtime_info.common.current_heating_state)
            if d.realtime_info and d.realtime_info.common else None
        ),
    ),
    EpluconSwitchDescription(
        key="warm_water_active",
        name="Warm Water Active",
        command="warm_water_active",
        read_fn=lambda d: (
            normalize_bool(d.realtime_info.common.warmwater)
            if d.realtime_info and d.realtime_info.common else None
        ),
    ),
    EpluconSwitchDescription(
        key="cooling_active",
        name="Cooling Active",
        command="cooling_active",
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    portal: EpluconPortalClient = hass.data[DOMAIN][f"{entry.entry_id}_portal"]

    entities: list[EpluconSwitchEntity] = []
    for device in coordinator.data:
        if isinstance(device, dict):
            device = from_dict(DeviceDTO, device)
        for description in SWITCH_DESCRIPTIONS:
            entities.append(EpluconSwitchEntity(coordinator, device, description, portal))

    _LOGGER.debug("Adding %d switch entities", len(entities))
    async_add_entities(entities)


class EpluconSwitchEntity(CoordinatorEntity, SwitchEntity):

    def __init__(
        self,
        coordinator,
        device: DeviceDTO,
        description: EpluconSwitchDescription,
        portal: EpluconPortalClient,
    ) -> None:
        super().__init__(coordinator)
        self.device = device
        self.entity_description = description
        self._portal = portal
        self._attr_name = description.name
        self._attr_unique_id = f"{device.id}_{description.key}"
        self._local_is_on: bool | None = None

    @property
    def device_info(self) -> dict:
        return {
            "manufacturer": MANUFACTURER,
            "identifiers": {(DOMAIN, self.device.account_module_index)},
        }

    @property
    def is_on(self) -> bool | None:
        desc: EpluconSwitchDescription = self.entity_description
        read_value = desc.read_fn(self.device)
        if read_value is not None:
            return read_value
        return self._local_is_on

    def _handle_coordinator_update(self) -> None:
        for updated in self.coordinator.data:
            if isinstance(updated, dict):
                updated = from_dict(DeviceDTO, updated)
            if updated.id == self.device.id:
                self.device = updated
                break
        super()._handle_coordinator_update()

    async def async_turn_on(self, **kwargs) -> None:
        await self._set(1)

    async def async_turn_off(self, **kwargs) -> None:
        await self._set(0)

    async def _set(self, value: int) -> None:
        desc: EpluconSwitchDescription = self.entity_description
        try:
            await self._portal.set_value(
                self.device.account_module_index,
                desc.command,
                value,
            )
        except PortalAuthError as err:
            raise HomeAssistantError(
                f"Portal login failed while setting {desc.name}: {err}"
            ) from err
        except PortalError as err:
            raise HomeAssistantError(f"Failed to set {desc.name}: {err}") from err

        self._local_is_on = bool(value)
        self.async_write_ha_state()