from __future__ import annotations

import aiohttp
import logging
from typing import Any

from .DTO.CommonInfoDTO import CommonInfoDTO
from .DTO.DeviceDTO import DeviceDTO
from .DTO.RealtimeInfoDTO import RealtimeInfoDTO
from .DTO.HeatLoadingDTO import HeatLoadingDTO
from .DTO.StatisticsDTO import StatisticsDTO

BASE_URL = "https://portaal.eplucon.nl/api/v2"

_LOGGER = logging.getLogger(__package__)


class ApiAuthError(Exception):
    """Authentication failed"""


class ApiError(Exception):
    """Generic API error"""


class EpluconApi:
    """Client to talk to the Eplucon API."""

    def __init__(
        self,
        api_token: str,
        api_endpoint: str | None = None,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        self._base = api_endpoint or BASE_URL

        if session is None:
            raise RuntimeError("aiohttp ClientSession is required")

        self._session = session
        self._headers = {
            "Accept": "application/json",
            "Cache-Control": "no-cache",
            "Authorization": f"Bearer {api_token}",
        }

        _LOGGER.debug(
            "Initialized Eplucon API client (endpoint=%s)",
            self._base,
        )



    async def get_devices(self) -> list[DeviceDTO]:
        url = f"{self._base}/econtrol/modules"
        _LOGGER.debug("Fetching devices list: %s", url)

        async with self._session.get(url, headers=self._headers) as response:
            data = await response.json()

        _LOGGER.debug("Devices raw response: %s", data)
        self._validate_response(data)

        devices: list[DeviceDTO] = []

        for item in data.get("data", []):
            try:
                devices.append(DeviceDTO(**item))
            except Exception:
                _LOGGER.exception("Failed to parse device DTO: %s", item)

        _LOGGER.debug("Parsed %d Eplucon devices", len(devices))
        return devices


    async def get_realtime_info(self, module_id: int) -> RealtimeInfoDTO:
        url = f"{self._base}/econtrol/modules/{module_id}/get_realtime_info"
        _LOGGER.debug("Fetching realtime info for %s: %s", module_id, url)

        async with self._session.get(url, headers=self._headers) as response:
            data = await response.json()

        _LOGGER.debug("Realtime raw response for %s: %s", module_id, data)
        self._validate_response(data)

        common = CommonInfoDTO(**data["data"]["common"])
        heatpump = data["data"].get("heatpump")

        return RealtimeInfoDTO(common=common, heatpump=heatpump)

    async def get_latest_statistics(self, module_id: int) -> StatisticsDTO | None:
        url = f"{self._base}/econtrol/modules/{module_id}/statistics"
        _LOGGER.debug("Fetching statistics for %s: %s", module_id, url)

        async with self._session.get(url, headers=self._headers) as response:
            data = await response.json()

        _LOGGER.debug("Statistics raw response for %s (truncated): %s", module_id, str(data)[:200])
        self._validate_response(data)

        records = data.get("data", {}).get("data", [])
        if not records:
            return None

        last = records[-1]

        def _tenth(key: str) -> float | None:
            val = last.get(key)
            if val is None or val == -9999:
                return None
            return round(val / 10, 1)

        def _float(key: str) -> float | None:
            val = last.get(key)
            return float(val) if val is not None else None

        return StatisticsDTO(
            heating_supply_setpoint=_float("Aanvoer setpoint verwarming"),
            cooling_supply_setpoint=_float("Aanvoer setpoint koeling"),
            zone_dg1_temperature=_tenth("Actuele temp. DG1"),
            zone_sg2_temperature=_tenth("Actuele temp. SG2"),
            zone_sg3_temperature=_tenth("Actuele temp. SG3"),
            zone_sg4_temperature=_tenth("Actuele temp. SG4"),
            heating_setpoint_dg1=_float("Setpoint verwarming DG1"),
            heating_setpoint_sg2=_float("Setpoint verwarming SG2"),
            heating_setpoint_sg3=_float("Setpoint verwarming SG3"),
            heating_setpoint_sg4=_float("Setpoint verwarming SG4"),
            cooling_setpoint_dg1=_float("Setpoint koeling DG1"),
            cooling_setpoint_sg2=_float("Setpoint koeling SG2"),
            cooling_setpoint_sg3=_float("Setpoint koeling SG3"),
            cooling_setpoint_sg4=_float("Setpoint koeling SG4"),
            valve_position_sg2=_float("Positie ventiel SG2"),
            valve_position_sg3=_float("Positie ventiel SG3"),
            valve_position_sg4=_float("Positie ventiel SG4"),
        )

    async def get_heatpump_heatloading_status(self, module_id: int) -> HeatLoadingDTO:
        url = f"{self._base}/econtrol/modules/{module_id}/heatloading_status"
        _LOGGER.debug("Fetching heatloading status for %s: %s", module_id, url)

        async with self._session.get(url, headers=self._headers) as response:
            data = await response.json()

        _LOGGER.debug("Heatloading raw response for %s: %s", module_id, data)
        self._validate_response(data)

        return HeatLoadingDTO(**data["data"])

    @staticmethod
    def _validate_response(response: Any) -> None:
        if not isinstance(response, dict):
            raise ApiError("Invalid API response type")

        if "auth" not in response:
            raise ApiError("Missing 'auth' field in API response")

        if response["auth"] is not True:
            raise ApiAuthError("Authentication failed")
