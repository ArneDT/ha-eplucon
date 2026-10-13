from __future__ import annotations

import asyncio
import json
import re
import logging
from typing import Any

import aiohttp

from ..const import EPLUCON_PORTAL_URL

_LOGGER = logging.getLogger(__name__)

# All writable commands with their portal code and validation metadata
COMMANDS: dict[str, dict[str, Any]] = {
    # Verwarming (Heating)
    "indoor_temperature": {"code": "5704", "type": "float", "min": 10.0, "max": 30.0},
    "heating_active": {"code": "5813", "type": "boolean", "min": 0, "max": 1},
    "stop_heating_above": {"code": "5814", "type": "float", "min": 0.0, "max": 30.0},
    "heating_auxiliary_electric": {"code": "5815", "type": "boolean", "min": 0, "max": 1},
    "heating_electric_emergency": {"code": "5816", "type": "boolean", "min": 0, "max": 1},
    "heating_curve_correction": {"code": "5886", "type": "enum", "min": 0, "max": 4},
    "heating_curve_correction_sg2": {"code": "5902", "type": "enum", "min": 0, "max": 4},
    "heating_curve_correction_sg3": {"code": "5903", "type": "enum", "min": 0, "max": 4},
    "heating_curve_correction_sg4": {"code": "5904", "type": "enum", "min": 0, "max": 4},
    # Koeling (Cooling)
    "cooling_active": {"code": "5817", "type": "boolean", "min": 0, "max": 1},
    "stop_active_cooling_below": {"code": "5818", "type": "float", "min": 0.0, "max": 35.0},
    "stop_passive_cooling_below": {"code": "5901", "type": "float", "min": 0.0, "max": 35.0},
    # Auto-WP (automatic heating/cooling switchover)
    "auto_wp_winter_start_temp": {"code": "5819", "type": "float", "min": -10.0, "max": 20.0},
    "auto_wp_summer_start_temp": {"code": "5820", "type": "float", "min": 20.0, "max": 40.0},
    "auto_wp_switchover_time": {"code": "5821", "type": "integer", "min": 1, "max": 24},
    # WW (Warm Water)
    "boiler_temperature": {"code": "5700", "type": "integer", "min": 0, "max": 65},
    "boiler_temperature_delta": {"code": "5804", "type": "float", "min": 5.0, "max": 65.0},
    "warm_water_active": {"code": "5711", "type": "boolean", "min": 0, "max": 1},
    "ww_electric_emergency": {"code": "5806", "type": "boolean", "min": 0, "max": 1},
    "ww_electric_support": {"code": "5805", "type": "boolean", "min": 0, "max": 1},
    # WW Weeksturing (weekly schedule)
    "ww_weekly_schedule_active": {"code": "5767", "type": "boolean", "min": 0, "max": 1},
    # Zwembad (Pool)
    "pool_active": {"code": "5905", "type": "boolean", "min": 0, "max": 1},
    "pool_temperature": {"code": "5906", "type": "float", "min": 15.0, "max": 40.0},
    "pool_winter_program_time": {"code": "5907", "type": "integer", "min": 1, "max": 60},
    # Warmtepomp
    "heatpump_active": {"code": "5715", "type": "enum", "min": 0, "max": 3},
    "heatpump_operation_mode": {"code": "5712", "type": "enum", "min": 1, "max": 5},
    # Energie-besparende modus (Energy saving mode)
    "energy_saving_threshold": {"code": "5758", "type": "float", "min": -10.0, "max": 10.0},
    "energy_saving_measure_time": {"code": "5759", "type": "integer", "min": 10, "max": 600},
    "energy_saving_mode_duration": {"code": "5879", "type": "integer", "min": 1, "max": 24},
    "energy_saving_ww_temperature": {"code": "5760", "type": "integer", "min": 45, "max": 75},
    "energy_saving_room_temp_calibration": {"code": "5761", "type": "float", "min": -5.0, "max": 5.0},
    # Vermogens-begrenzing (Power limiting)
    "power_limit": {"code": "5775", "type": "float", "min": 0.0, "max": 15.0},
    "power_limit_hysteresis": {"code": "5776", "type": "float", "min": 0.0, "max": 5.0},
    "power_limit_activation_time": {"code": "5777", "type": "integer", "min": 1, "max": 60},
}

# Maps command type → (format value, type value, blockType value) for the portal payload
_PAYLOAD_META: dict[str, tuple[str, str, str]] = {
    "float":   ("2", "2",  "menu"),
    "integer": ("1", "1",  "module"),
    "boolean": ("0", "10", "menu"),
    "enum":    ("0", "11", "menu"),
}


class PortalAuthError(Exception):
    """Portal login failed."""


class PortalError(Exception):
    """Generic portal communication error."""


class EpluconPortalClient:
    """Write values to the Eplucon heatpump via web-portal scraping.

    Eplucon's official REST API is read-only. This client works around
    that by replaying the browser flow that the portal web UI uses.
    It is inherently fragile and will break if Eplucon changes their
    portal HTML structure.
    """

    def __init__(
        self,
        username: str,
        password: str,
        portal_url: str = EPLUCON_PORTAL_URL,
    ) -> None:
        self._username = username
        self._password = password
        self._base = portal_url.rstrip("/")
        # Dedicated session so portal cookies never leak into HA's shared session.
        self._session = aiohttp.ClientSession()
        # Serialise the full login→fetch→post sequence to prevent session-cookie races
        # when multiple write entities fire concurrently.
        self._lock = asyncio.Lock()

    async def async_close(self) -> None:
        """Close the underlying HTTP session. Call from async_unload_entry."""
        if not self._session.closed:
            await self._session.close()

    async def async_verify_credentials(self) -> None:
        """Attempt a portal login to validate credentials.

        Raises PortalAuthError on invalid credentials, PortalError on other failure.
        """
        async with self._lock:
            await self._login()

    async def set_value(
        self,
        account_module_index: str,
        command: str,
        value: Any,
    ) -> None:
        """Write a value to the heatpump.

        Raises PortalAuthError on login failure, PortalError on other failure.
        """
        if command not in COMMANDS:
            raise PortalError(f"Unknown command: {command}")

        cmd = COMMANDS[command]
        url_modal = (
            f"{self._base}/e-control/ajax/modal/{cmd['code']}"
            f"?blockType=module&account_module_index={account_module_index}"
        )
        url_send = (
            f"{self._base}/e-control/ajax/send_control_data"
            f"?account_module_index={account_module_index}"
        )

        # Hold the lock for the entire login → fetch modal → post sequence so that
        # concurrent writes cannot interleave their session cookies.
        async with self._lock:
            await self._login()

            async with self._session.get(url_modal) as response:
                if response.status != 200:
                    raise PortalError(
                        f"Failed to fetch control form for {command} "
                        f"(HTTP {response.status}) — check account_module_index"
                    )
                html = await response.text()

            json_data = _build_json_payload(cmd, value)
            form = _extract_escaped_form_fields(html)
            form["data"] = json_data

            async with self._session.post(url_send, data=form) as response:
                if response.status != 200:
                    raise PortalError(
                        f"Failed to set {command}={value} (HTTP {response.status})"
                    )

        _LOGGER.debug(
            "Set %s=%s for module %s via portal",
            command,
            value,
            account_module_index,
        )

    async def _login(self) -> None:
        """Perform portal login, leaving the session authenticated."""
        url_auth = f"{self._base}/login"

        async with self._session.get(url_auth) as response:
            if response.status != 200:
                raise PortalError(
                    f"Failed to reach login page (HTTP {response.status})"
                )
            html = await response.text()

        form = _extract_form_fields(html)
        form["username"] = self._username
        form["password"] = self._password

        async with self._session.post(url_auth, data=form) as response:
            if response.status != 200:
                raise PortalError(f"Login POST failed (HTTP {response.status})")
            html = await response.text()
            final_url = str(response.url)

        # A successful login redirects away from /login; failure stays on it.
        # Keep the Dutch string check as a belt-and-suspenders fallback.
        if final_url.startswith(url_auth) or "inloggegevens is niet" in html:
            raise PortalAuthError("Portal login failed: invalid credentials")


def _build_json_payload(cmd: dict[str, Any], value: Any) -> str:
    """Build the portal control payload using json.dumps to avoid injection via str replace."""
    fmt, type_val, block_type = _PAYLOAD_META[cmd["type"]]
    return json.dumps([
        {"name": "format",     "value": fmt},
        {"name": "type",       "value": type_val},
        {"name": "menutype",   "value": "MU"},
        {"name": "blockType",  "value": block_type},
        {"name": "tile_value", "value": str(value)},
        {"name": "ido",        "value": cmd["code"]},
    ])


def _extract_form_fields(html: str) -> dict[str, str]:
    """Extract name/value pairs from plain HTML <input> tags."""
    fields: dict[str, str] = {}
    for tag in re.findall(r"<input[^>]*>", html):
        name_m = re.search(r'name="([^"]*)"', tag)
        value_m = re.search(r'value="([^"]*)"', tag)
        if name_m:
            fields[name_m.group(1)] = value_m.group(1) if value_m else ""
    return fields


def _extract_escaped_form_fields(html: str) -> dict[str, str]:
    """Extract name/value pairs from JSON-escaped HTML (modal AJAX response).

    The closing delimiter is \\\" (backslash + quote), so the capture group
    must exclude backslashes to avoid capturing the trailing \\ before the
    closing quote.
    """
    fields: dict[str, str] = {}
    for tag in re.findall(r"<input[^>]*>", html):
        name_m = re.search(r'name=\\"([^"\\]*)\\"', tag)
        value_m = re.search(r'value=\\"([^"\\]*)\\"', tag)
        if name_m:
            fields[name_m.group(1)] = value_m.group(1) if value_m else ""
    return fields
