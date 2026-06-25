from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable

from dacite import from_dict
from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .eplucon_api.DTO.DeviceDTO import DeviceDTO
from .eplucon_api.eplucon_portal_client import EpluconPortalClient, PortalAuthError, PortalError

_LOGGER = logging.getLogger(__name__)


@dataclass(kw_only=True)
class EpluconSelectDescription(SelectEntityDescription):
    command: str
    option_to_value: dict[str, int]
    read_fn: Callable[[DeviceDTO], str | None] = field(default=lambda _: None)


_HEATPUMP_ACTIVE_OPTIONS = ["Disabled", "Enabled", "Emergency", "APX"]
_HEATPUMP_ACTIVE_TO_VALUE = {label: i for i, label in enumerate(_HEATPUMP_ACTIVE_OPTIONS)}
_VALUE_TO_HEATPUMP_ACTIVE = {v: k for k, v in _HEATPUMP_ACTIVE_TO_VALUE.items()}

_OPERATION_MODE_OPTIONS = ["Cooling", "Heating", "Auto th-TOUCH", "Auto Wp", "Fireplace"]
_OPERATION_MODE_TO_VALUE = {label: i + 1 for i, label in enumerate(_OPERATION_MODE_OPTIONS)}
_VALUE_TO_OPERATION_MODE = {v: k for k, v in _OPERATION_MODE_TO_VALUE.items()}


SELECT_DESCRIPTIONS: list[EpluconSelectDescription] = [
    EpluconSelectDescription(
        key="heatpump_active",
        name="Heatpump State",
        command="heatpump_active",
        options=_HEATPUMP_ACTIVE_OPTIONS,
        option_to_value=_HEATPUMP_ACTIVE_TO_VALUE,
        read_fn=lambda d: (
            _VALUE_TO_HEATPUMP_ACTIVE.get(int(d.realtime_info.common.heating_mode))
            if d.realtime_info and d.realtime_info.common
            and d.realtime_info.common.heating_mode is not None
            else None
        ),
    ),
    EpluconSelectDescription(
        key="heatpump_operation_mode",
        name="Operation Mode",
        command="heatpump_operation_mode",
        options=_OPERATION_MODE_OPTIONS,
        option_to_value=_OPERATION_MODE_TO_VALUE,
        read_fn=lambda d: (
            _VALUE_TO_OPERATION_MODE.get(int(d.realtime_info.common.operation_mode))
            if d.realtime_info and d.realtime_info.common
            and d.realtime_info.common.operation_mode is not None
            else None
        ),
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    portal: EpluconPortalClient = hass.data[DOMAIN][f"{entry.entry_id}_portal"]

    entities: list[EpluconSelectEntity] = []
    for device in coordinator.data:
        if isinstance(device, dict):
            device = from_dict(DeviceDTO, device)
        for description in SELECT_DESCRIPTIONS:
            entities.append(EpluconSelectEntity(coordinator, device, description, portal))

    _LOGGER.debug("Adding %d select entities", len(entities))
    async_add_entities(entities)


class EpluconSelectEntity(CoordinatorEntity, SelectEntity):

    def __init__(
        self,
        coordinator,
        device: DeviceDTO,
        description: EpluconSelectDescription,
        portal: EpluconPortalClient,
    ) -> None:
        super().__init__(coordinator)
        self.device = device
        self.entity_description = description
        self._portal = portal
        self._attr_name = description.name
        self._attr_unique_id = f"{device.id}_{description.key}"
        self._local_option: str | None = None

    @property
    def device_info(self) -> dict:
        return {
            "manufacturer": MANUFACTURER,
            "identifiers": {(DOMAIN, self.device.account_module_index)},
        }

    @property
    def current_option(self) -> str | None:
        desc: EpluconSelectDescription = self.entity_description
        read_value = desc.read_fn(self.device)
        if read_value is not None:
            return read_value
        return self._local_option

    def _handle_coordinator_update(self) -> None:
        for updated in self.coordinator.data:
            if isinstance(updated, dict):
                updated = from_dict(DeviceDTO, updated)
            if updated.id == self.device.id:
                self.device = updated
                break
        super()._handle_coordinator_update()

    async def async_select_option(self, option: str) -> None:
        desc: EpluconSelectDescription = self.entity_description
        value = desc.option_to_value.get(option)
        if value is None:
            raise HomeAssistantError(f"Unknown option '{option}' for {desc.name}")

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

        self._local_option = option
        self.async_write_ha_state()