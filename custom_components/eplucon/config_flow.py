import logging
import voluptuous as vol
from typing import Any, Dict, Optional
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import aiohttp_client
from homeassistant.data_entry_flow import FlowResult
from .const import (
    DOMAIN,
    SUPPORTED_TYPES,
    CONF_PORTAL_USERNAME,
    CONF_PORTAL_PASSWORD,
    CONF_PORTAL_URL,
    EPLUCON_PORTAL_URL,
)
from .eplucon_api.eplucon_client import EpluconApi, ApiAuthError, ApiError, BASE_URL
from .eplucon_api.eplucon_portal_client import (
    EpluconPortalClient,
    PortalAuthError,
    PortalError,
)

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA_USER = vol.Schema({
    vol.Required("api_token"): str,
    vol.Required("api_endpoint", default=BASE_URL): str,
})

DATA_SCHEMA_PORTAL = vol.Schema({
    vol.Optional(CONF_PORTAL_USERNAME, default=""): str,
    vol.Optional(CONF_PORTAL_PASSWORD, default=""): str,
    vol.Optional(CONF_PORTAL_URL, default=EPLUCON_PORTAL_URL): str,
})


class EpluconConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Eplucon."""

    VERSION = 1

    def __init__(self) -> None:
        self._api_data: dict[str, Any] = {}

    async def async_step_user(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Step 1: API token + endpoint."""
        errors: Dict[str, str] = {}

        if user_input is not None:
            api_token: str = user_input["api_token"]
            api_endpoint: str = user_input["api_endpoint"]
            session = aiohttp_client.async_get_clientsession(self.hass)
            client = EpluconApi(api_token, api_endpoint, session)

            try:
                devices = await client.get_devices()
                devices = [d for d in devices if d.type in SUPPORTED_TYPES]

                if devices:
                    self._api_data = {
                        "api_token": api_token,
                        "api_endpoint": api_endpoint,
                        "devices": devices,
                    }
                    return await self.async_step_portal()

                errors["base"] = "no-devices"

            except ApiAuthError:
                errors["base"] = "auth"
            except ApiError:
                errors["base"] = "api"
            except Exception:
                _LOGGER.exception("Unexpected exception during config flow")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA_USER,
            errors=errors,
        )

    async def async_step_portal(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Step 2 (optional): Portal credentials for write access."""
        errors: Dict[str, str] = {}

        if user_input is not None:
            username = user_input.get(CONF_PORTAL_USERNAME, "").strip()
            password = user_input.get(CONF_PORTAL_PASSWORD, "").strip()
            portal_url = user_input.get(CONF_PORTAL_URL, EPLUCON_PORTAL_URL).strip()

            if bool(username) != bool(password):
                errors["base"] = "portal_incomplete"
            elif username and password:
                portal = EpluconPortalClient(username, password, portal_url)
                try:
                    await portal.async_verify_credentials()
                    self._api_data[CONF_PORTAL_USERNAME] = username
                    self._api_data[CONF_PORTAL_PASSWORD] = password
                    self._api_data[CONF_PORTAL_URL] = portal_url
                except PortalAuthError:
                    errors["base"] = "portal_auth"
                except PortalError:
                    errors["base"] = "portal_error"
                except Exception:
                    _LOGGER.exception("Unexpected exception verifying portal credentials")
                    errors["base"] = "unknown"
                finally:
                    await portal.async_close()

            if not errors:
                return self.async_create_entry(title="Eplucon", data=self._api_data)

        return self.async_show_form(
            step_id="portal",
            data_schema=DATA_SCHEMA_PORTAL,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> config_entries.OptionsFlow:
        return EpluconOptionsFlowHandler(config_entry)


class EpluconOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle Eplucon options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        super().__init__()
        self._config_entry = config_entry

    async def async_step_init(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Manage options: API token/endpoint and portal credentials."""
        errors: Dict[str, str] = {}
        entry = self._config_entry

        if user_input is not None:
            api_token = user_input.get("api_token", "")
            api_endpoint = user_input.get("api_endpoint", BASE_URL)
            username = user_input.get(CONF_PORTAL_USERNAME, "").strip()
            password = user_input.get(CONF_PORTAL_PASSWORD, "").strip()
            portal_url = user_input.get(CONF_PORTAL_URL, EPLUCON_PORTAL_URL).strip()

            session = aiohttp_client.async_get_clientsession(self.hass)
            client = EpluconApi(api_token, api_endpoint, session)

            try:
                devices = await client.get_devices()
                devices = [d for d in devices if d.type in SUPPORTED_TYPES]

                if not devices:
                    errors["base"] = "no-devices"
                else:
                    new_data: dict[str, Any] = {
                        "api_token": api_token,
                        "api_endpoint": api_endpoint,
                        "devices": devices,
                    }

                    if bool(username) != bool(password):
                        errors["base"] = "portal_incomplete"
                    elif username and password:
                        portal = EpluconPortalClient(username, password, portal_url)
                        try:
                            await portal.async_verify_credentials()
                            new_data[CONF_PORTAL_USERNAME] = username
                            new_data[CONF_PORTAL_PASSWORD] = password
                            new_data[CONF_PORTAL_URL] = portal_url
                        except PortalAuthError:
                            errors["base"] = "portal_auth"
                        except PortalError:
                            errors["base"] = "portal_error"
                        except Exception:
                            _LOGGER.exception("Unexpected exception verifying portal credentials")
                            errors["base"] = "unknown"
                        finally:
                            await portal.async_close()

                    if not errors:
                        self.hass.config_entries.async_update_entry(entry, data=new_data)
                        return self.async_create_entry(title="", data={})

            except ApiAuthError:
                errors["base"] = "auth"
            except ApiError:
                errors["base"] = "api"
            except Exception:
                _LOGGER.exception("Unexpected exception in options flow")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required("api_token", default=entry.data.get("api_token", "")): str,
                vol.Required("api_endpoint", default=entry.data.get("api_endpoint", BASE_URL)): str,
                vol.Optional(CONF_PORTAL_USERNAME, default=entry.data.get(CONF_PORTAL_USERNAME, "")): str,
                vol.Optional(CONF_PORTAL_PASSWORD, default=entry.data.get(CONF_PORTAL_PASSWORD, "")): str,
                vol.Optional(CONF_PORTAL_URL, default=entry.data.get(CONF_PORTAL_URL, EPLUCON_PORTAL_URL)): str,
            }),
            errors=errors,
        )
