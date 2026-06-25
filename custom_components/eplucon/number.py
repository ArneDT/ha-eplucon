from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable

from dacite import from_dict
from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .eplucon_api.DTO.DeviceDTO import DeviceDTO
from .eplucon_api.eplucon_portal_client import EpluconPortalClient, PortalAuthError, PortalError

_LOGGER = logging.getLogger(__name__)


@dataclass(kw_only=True)
class EpluconNumberDescription(NumberEntityDescription):
    command: str
    read_fn: Callable[[DeviceDTO], float | None] = field(default=lambda _: None)


NUMBER_DESCRIPTIONS: list[EpluconNumberDescription] = [
    EpluconNumberDescription(
        key="indoor_temperature_setpoint",
        name="Indoor Temperature Setpoint",
        command="indoor_temperature",
        native_min_value=10.0,
        native_max_value=30.0,
        native_step=0.5,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        read_fn=lambda d: (
            float(d.realtime_info.common.configured_indoor_temperature)
            if d.realtime_info and d.realtime_info.common
            and d.realtime_info.common.configured_indoor_temperature is not None
            else None
        ),
    ),
    EpluconNumberDescription(
        key="boiler_temperature_setpoint",
        name="Boiler Temperature",
        command="boiler_temperature",
        native_min_value=10.0,
        native_max_value=65.0,
        native_step=1.0,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        read_fn=lambda d: (
            float(d.realtime_info.common.ww_temperature_configured)
            if d.realtime_info and d.realtime_info.common
            and d.realtime_info.common.ww_temperature_configured is not None
            else None
        ),
    ),
    EpluconNumberDescription(
        key="boiler_temperature_delta",
        name="Boiler Temperature Delta",
        command="boiler_temperature_delta",
        native_min_value=5.0,
        native_max_value=65.0,
        native_step=0.5,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    EpluconNumberDescription(
        key="stop_heating_above",
        name="Stop Heating Above",
        command="stop_heating_above",
        native_min_value=0.0,
        native_max_value=30.0,
        native_step=0.5,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    EpluconNumberDescription(
        key="heating_curve_correction",
        name="Heating Curve Correction",
        command="heating_curve_correction",
        native_min_value=0,
        native_max_value=4,
        native_step=1,
    ),
    EpluconNumberDescription(
        key="stop_passive_cooling_below",
        name="Stop Passive Cooling Below",
        command="stop_passive_cooling_below",
        native_min_value=0.0,
        native_max_value=35.0,
        native_step=0.5,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    EpluconNumberDescription(
        key="stop_active_cooling_below",
        name="Stop Active Cooling Below",
        command="stop_active_cooling_below",
        native_min_value=0.0,
        native_max_value=35.0,
        native_step=0.5,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    portal: EpluconPortalClient = hass.data[DOMAIN][f"{entry.entry_id}_portal"]

    entities: list[EpluconNumberEntity] = []
    for device in coordinator.data:
        if isinstance(device, dict):
            device = from_dict(DeviceDTO, device)
        for description in NUMBER_DESCRIPTIONS:
            entities.append(EpluconNumberEntity(coordinator, device, description, portal))

    _LOGGER.debug("Adding %d number entities", len(entities))
    async_add_entities(entities)


class EpluconNumberEntity(CoordinatorEntity, NumberEntity):
    _attr_mode = NumberMode.BOX

    def __init__(
        self,
        coordinator,
        device: DeviceDTO,
        description: EpluconNumberDescription,
        portal: EpluconPortalClient,
    ) -> None:
        super().__init__(coordinator)
        self.device = device
        self.entity_description = description
        self._portal = portal
        self._attr_name = description.name
        self._attr_unique_id = f"{device.id}_{description.key}"
        self._local_value: float | None = None

    @property
    def device_info(self) -> dict:
        return {
            "manufacturer": MANUFACTURER,
            "identifiers": {(DOMAIN, self.device.account_module_index)},
        }

    @property
    def native_value(self) -> float | None:
        desc: EpluconNumberDescription = self.entity_description
        read_value = desc.read_fn(self.device)
        if read_value is not None:
            return read_value
        return self._local_value

    def _handle_coordinator_update(self) -> None:
        for updated in self.coordinator.data:
            if isinstance(updated, dict):
                updated = from_dict(DeviceDTO, updated)
            if updated.id == self.device.id:
                self.device = updated
                break
        super()._handle_coordinator_update()

    async def async_set_native_value(self, value: float) -> None:
        desc: EpluconNumberDescription = self.entity_description
        cmd_value = int(value) if desc.native_step == 1 else value
        try:
            await self._portal.set_value(
                self.device.account_module_index,
                desc.command,
                cmd_value,
            )
        except PortalAuthError as err:
            raise HomeAssistantError(
                f"Portal login failed while setting {desc.name}: {err}"
            ) from err
        except PortalError as err:
            raise HomeAssistantError(
                f"Failed to set {desc.name}: {err}"
            ) from err

        self._local_value = value
        self.async_write_ha_state()
