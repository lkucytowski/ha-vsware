"""Sensor platform for VSware."""
from __future__ import annotations

import logging
import re
from datetime import timedelta

import aiohttp

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .config_flow import derive_api_base_url
from .const import (
    ATTENDANCE_PATH,
    BEHAVIOUR_PATH,
    CONF_DISPLAY_NAME,
    CONF_LEARNER_ID,
    CONF_PARENT_ID,
    CONF_PASSWORD,
    CONF_PREFERRED_NAME,
    CONF_USERNAME,
    CONF_WEBSITE_URL,
    DOMAIN,
    LOGIN_PATH,
)

_LOGGER = logging.getLogger(__name__)

_ATTENDANCE_LIST_SENSORS = [
    ("unexplainedAbsences", "Unexplained Absences", "unexplained_absences", "mdi:help-circle"),
    ("presentDays",         "Present Days",         "present_days",         "mdi:check-circle"),
    ("absentDays",          "Absent Days",          "absent_days",          "mdi:close-circle"),
    ("partiallyAbsentDays", "Partially Absent Days","partially_absent_days","mdi:minus-circle"),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up VSware sensors from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    entities: list[SensorEntity] = [VswareTotalSchoolDaysSensor(coordinator, entry)]
    for data_key, name, slug, icon in _ATTENDANCE_LIST_SENSORS:
        entities.append(VswareAttendanceListSensor(coordinator, entry, data_key, name, slug, icon))
    entities.append(VswareBehaviourPointsSensor(coordinator, entry, "positivePoints", "Positive Points", "positive_points", "mdi:thumb-up"))
    entities.append(VswareBehaviourPointsSensor(coordinator, entry, "negativePoints", "Negative Points", "negative_points", "mdi:thumb-down"))
    entities.append(VswareLatestBehaviourSensor(coordinator, entry))
    entities.append(VswareProgressScoreSensor(coordinator, entry))
    async_add_entities(entities)


class VswareCoordinator(DataUpdateCoordinator):
    """Coordinator to manage fetching data from the VSware API."""

    def __init__(self, hass: HomeAssistant, config: dict, scan_interval: int) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )
        self._api_base_url = derive_api_base_url(config[CONF_WEBSITE_URL])
        self._username = config[CONF_USERNAME]
        self._password = config[CONF_PASSWORD]
        self._learner_id = str(config[CONF_LEARNER_ID])
        self._parent_id = config[CONF_PARENT_ID]
        self._token: str | None = None

    async def _async_login(self) -> None:
        """Authenticate and store the token."""
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self._api_base_url}{LOGIN_PATH}",
                json={"username": self._username, "password": self._password, "source": "web"},
                headers={"Content-Type": "application/json"},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                response.raise_for_status()
                token = response.headers.get("Authorization")
                if not token:
                    raise UpdateFailed("Login succeeded but no Authorization token received")
                self._token = token

    async def _async_update_data(self) -> dict:
        """Fetch attendance and behaviour data."""
        attendance_url = self._api_base_url + ATTENDANCE_PATH.format(
            learner_id=self._learner_id, parent_id=self._parent_id
        )
        behaviour_url = f"{self._api_base_url}{BEHAVIOUR_PATH}"

        async with aiohttp.ClientSession() as session:
            try:
                attendance = await self._async_fetch_get(session, attendance_url)
                behaviour = await self._async_fetch_behaviour(session, behaviour_url)
                return {"attendance": attendance, "behaviour": behaviour}
            except aiohttp.ClientResponseError as err:
                if err.status == 401:
                    self._token = None
                    await self._async_login()
                    attendance = await self._async_fetch_get(session, attendance_url)
                    behaviour = await self._async_fetch_behaviour(session, behaviour_url)
                    return {"attendance": attendance, "behaviour": behaviour}
                raise UpdateFailed(f"API error {err.status}: {err.message}") from err
            except aiohttp.ClientError as err:
                raise UpdateFailed(f"Error communicating with API: {err}") from err

    async def _async_fetch_get(self, session: aiohttp.ClientSession, url: str) -> dict:
        """GET a URL, logging in first if no token."""
        if not self._token:
            await self._async_login()
        async with session.get(
            url,
            headers={"Authorization": self._token, "Content-Type": "application/json"},
            timeout=aiohttp.ClientTimeout(total=10),
        ) as response:
            response.raise_for_status()
            return await response.json()

    async def _async_fetch_behaviour(self, session: aiohttp.ClientSession, url: str) -> dict | None:
        """POST behaviour endpoint with learnerId, filter result to this learner."""
        if not self._token:
            await self._async_login()
        async with session.post(
            url,
            headers={"Authorization": self._token, "Content-Type": "application/json"},
            data=self._learner_id,
            timeout=aiohttp.ClientTimeout(total=10),
        ) as response:
            response.raise_for_status()
            raw = await response.json()

        # The API may return a list (multiple children) or a single object.
        if isinstance(raw, list):
            match = next((item for item in raw if str(item.get("id")) == self._learner_id), None)
            if match is None:
                _LOGGER.warning("Behaviour response contained no entry for learnerId %s", self._learner_id)
            return match
        # Single object — verify it belongs to this learner before returning.
        if str(raw.get("id")) != self._learner_id:
            _LOGGER.warning(
                "Behaviour response id %s does not match learnerId %s",
                raw.get("id"),
                self._learner_id,
            )
            return None
        return raw


def _entity_slug(entry: ConfigEntry) -> str:
    """Return a sanitized slug for entity_id construction (preferredGivenName or learner_id)."""
    name = entry.data.get(CONF_PREFERRED_NAME) or str(entry.data[CONF_LEARNER_ID])
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def _device_info(entry: ConfigEntry) -> DeviceInfo:
    learner_id = entry.data[CONF_LEARNER_ID]
    display_name = entry.data.get(CONF_DISPLAY_NAME, f"Student {learner_id}")
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name=f"VSware – {display_name}",
        manufacturer="VSware",
        model="Attendance Monitor",
    )


class VswareTotalSchoolDaysSensor(CoordinatorEntity, SensorEntity):
    """Sensor entity for total school days."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:school"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "days"

    def __init__(self, coordinator: VswareCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_total_school_days"
        self._attr_name = "Total School Days"
        self.entity_id = f"sensor.vsware_{_entity_slug(entry)}_total_school_days"
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self) -> int | None:
        """Return total school days."""
        attendance = (self.coordinator.data or {}).get("attendance")
        if attendance is None:
            return None
        return attendance.get("totalSchoolDays")


class VswareAttendanceListSensor(CoordinatorEntity, SensorEntity):
    """Sensor that exposes a count and date list for an attendance field."""

    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "days"

    def __init__(
        self,
        coordinator: VswareCoordinator,
        entry: ConfigEntry,
        data_key: str,
        name: str,
        slug: str,
        icon: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._data_key = data_key
        self._attr_unique_id = f"{entry.entry_id}_{slug}"
        self._attr_name = name
        self._attr_icon = icon
        self.entity_id = f"sensor.vsware_{_entity_slug(entry)}_{slug}"
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self) -> int | None:
        """Return the count of days in the list."""
        attendance = (self.coordinator.data or {}).get("attendance")
        if attendance is None:
            return None
        return len(attendance.get(self._data_key, []))

    @property
    def extra_state_attributes(self) -> dict | None:
        """Return the list of dates as an attribute."""
        attendance = (self.coordinator.data or {}).get("attendance")
        if attendance is None:
            return None
        return {"dates": attendance.get(self._data_key, [])}


class VswareBehaviourPointsSensor(CoordinatorEntity, SensorEntity):
    """Sensor for positive or negative behaviour points."""

    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "points"

    def __init__(
        self,
        coordinator: VswareCoordinator,
        entry: ConfigEntry,
        data_key: str,
        name: str,
        slug: str,
        icon: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._data_key = data_key
        self._attr_unique_id = f"{entry.entry_id}_{slug}"
        self._attr_name = name
        self._attr_icon = icon
        self.entity_id = f"sensor.vsware_{_entity_slug(entry)}_{slug}"
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self) -> int | None:
        """Return the behaviour points value."""
        behaviour = (self.coordinator.data or {}).get("behaviour")
        if behaviour is None:
            return None
        return behaviour.get(self._data_key)


class VswareLatestBehaviourSensor(CoordinatorEntity, SensorEntity):
    """Sensor for the most recent behaviour entry."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:star"

    def __init__(self, coordinator: VswareCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._learner_id = str(entry.data[CONF_LEARNER_ID])
        self._attr_unique_id = f"{entry.entry_id}_latest_behaviour"
        self._attr_name = "Most Recent Points"
        self.entity_id = f"sensor.vsware_{_entity_slug(entry)}_most_recent_points"
        self._attr_device_info = _device_info(entry)

    def _latest_entry(self) -> dict | None:
        """Return the most recent collection entry for this learner."""
        behaviour = (self.coordinator.data or {}).get("behaviour")
        if not behaviour:
            return None
        entries = [
            e for e in behaviour.get("collection", [])
            if str(e.get("learnerId")) == self._learner_id
        ]
        return entries[0] if entries else None

    @property
    def native_value(self) -> str | None:
        """Return 'positive' or 'negative' based on the latest entry."""
        entry = self._latest_entry()
        if entry is None:
            return None
        value = entry.get("behaviourEntry", {}).get("positiveOrNegative")
        return value.capitalize() if value else None

    @property
    def extra_state_attributes(self) -> dict | None:
        """Return details of the latest behaviour entry."""
        entry = self._latest_entry()
        if entry is None:
            return None
        be = entry.get("behaviourEntry", {})
        return {
            "points": be.get("behaviourPoints"),
            "subject": entry.get("subjectName"),
            "comment": entry.get("behaviourNote"),
            "date": entry.get("createdDate"),
            "raised_by": entry.get("creatorName"),
        }


class VswareProgressScoreSensor(CoordinatorEntity, SensorEntity):
    """Sensor for the progress score (startingPoints + totalPoints)."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:trending-up"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "points"

    def __init__(self, coordinator: VswareCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_progress_score"
        self._attr_name = "Progress Score"
        self.entity_id = f"sensor.vsware_{_entity_slug(entry)}_progress_score"
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self) -> int | None:
        """Return startingPoints + totalPoints."""
        behaviour = (self.coordinator.data or {}).get("behaviour")
        if behaviour is None:
            return None
        starting = behaviour.get("startingPoints") or 0
        total = behaviour.get("totalPoints") or 0
        return starting + total
