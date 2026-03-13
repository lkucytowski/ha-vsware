"""Config flow for VSware integration."""
from __future__ import annotations

import aiohttp
import voluptuous as vol

from homeassistant import config_entries

from .const import (
    CONF_DISPLAY_NAME,
    derive_api_base_url,
    CONF_LEARNER_ID,
    CONF_ACADEMIC_YEAR_ID,
    CONF_PREFERRED_NAME,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
    CONF_WEBSITE_URL,
    DEFAULT_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
    DOMAIN,
    LEARNERS_PATH,
    LOGIN_PATH,
    SECURITY_ROLES_PATH,
)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_WEBSITE_URL): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): int,
    }
)



class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for VSware."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialise."""
        self._data: dict = {}
        self._token: str | None = None
        self._learners: list[dict] = []

    async def async_step_user(self, user_input=None):
        """Step 1: collect credentials, then fetch academic year ID and learners."""
        errors: dict[str, str] = {}

        if user_input is not None:
            if user_input.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL) < MIN_SCAN_INTERVAL:
                errors[CONF_SCAN_INTERVAL] = "scan_interval_too_low"
            else:
                api_base_url = derive_api_base_url(user_input[CONF_WEBSITE_URL])
                token = await self._async_login(api_base_url, user_input[CONF_USERNAME], user_input[CONF_PASSWORD])
                if token is None:
                    errors["base"] = "invalid_auth"
                else:
                    self._token = token
                    academic_year_id = await self._async_fetch_academic_year_id(api_base_url, token)
                    if academic_year_id is None:
                        errors["base"] = "cannot_fetch_user"
                    else:
                        self._learners = await self._async_fetch_learners(api_base_url, token)
                        if not self._learners:
                            errors["base"] = "no_learners"
                        else:
                            self._data = {**user_input, CONF_ACADEMIC_YEAR_ID: str(academic_year_id)}
                            return await self.async_step_select_learner()

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_select_learner(self, user_input=None):
        """Step 2: pick a learner from the list."""
        errors: dict[str, str] = {}

        learner_options = {str(l["learnerId"]): l["displayName"] for l in self._learners}

        if user_input is not None:
            learner_id = user_input[CONF_LEARNER_ID]
            display_name = learner_options[learner_id]
            learner = next((l for l in self._learners if str(l["learnerId"]) == learner_id), {})
            preferred_name = learner.get("preferredGivenName") or learner.get("givenName") or learner_id
            data = {
                **self._data,
                CONF_LEARNER_ID: learner_id,
                CONF_DISPLAY_NAME: display_name,
                CONF_PREFERRED_NAME: preferred_name,
            }
            await self.async_set_unique_id(f"{data[CONF_ACADEMIC_YEAR_ID]}_{learner_id}")
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=f"VSware – {display_name}", data=data)

        schema = vol.Schema({vol.Required(CONF_LEARNER_ID): vol.In(learner_options)})
        return self.async_show_form(
            step_id="select_learner",
            data_schema=schema,
            errors=errors,
        )

    async def _async_login(self, api_base_url: str, username: str, password: str) -> str | None:
        """Attempt login and return the token, or None on failure."""
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(
                    f"{api_base_url}{LOGIN_PATH}",
                    json={"username": username, "password": password, "source": "web"},
                    headers={"Content-Type": "application/json"},
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as response:
                    if response.status == 200:
                        return response.headers.get("Authorization")
                    return None
            except aiohttp.ClientError:
                return None

    async def _async_fetch_academic_year_id(self, api_base_url: str, token: str) -> int | None:
        """Fetch the academicYearId from the security roles endpoint."""
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(
                    f"{api_base_url}{SECURITY_ROLES_PATH}",
                    headers={"Authorization": token, "Content-Type": "application/json"},
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as response:
                    response.raise_for_status()
                    data = await response.json()
                    return data.get("academicYearId")
            except aiohttp.ClientError:
                return None

    async def _async_fetch_learners(self, api_base_url: str, token: str) -> list[dict]:
        """Fetch the list of learners for this household."""
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(
                    f"{api_base_url}{LEARNERS_PATH}",
                    headers={"Authorization": token, "Content-Type": "application/json"},
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as response:
                    response.raise_for_status()
                    return await response.json()
            except aiohttp.ClientError:
                return []
