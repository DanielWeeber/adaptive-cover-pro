"""Binary Sensor platform for the Adaptive Cover Pro integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_ALARM_ENTITY, CONF_ENABLE_DIAGNOSTICS, DOMAIN
from .coordinator import AdaptiveDataUpdateCoordinator
from .entity_base import AdaptiveCoverBaseEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Adaptive Cover Pro binary sensor platform."""
    coordinator: AdaptiveDataUpdateCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ]

    entities = []

    binary_sensor = AdaptiveCoverBinarySensor(
        config_entry,
        config_entry.entry_id,
        "Sun Infront",
        False,
        "sun_motion",
        BinarySensorDeviceClass.MOTION,
        coordinator,
    )
    manual_override = AdaptiveCoverBinarySensor(
        config_entry,
        config_entry.entry_id,
        "Manual Override",
        False,
        "manual_override",
        BinarySensorDeviceClass.RUNNING,
        coordinator,
    )
    entities.extend([binary_sensor, manual_override])

    # "Paused by Alarm" sensor — only shown when alarm entity is configured
    if config_entry.options.get(CONF_ALARM_ENTITY):
        alarm_inhibited_sensor = AlarmInhibitedBinarySensor(
            config_entry,
            config_entry.entry_id,
            coordinator,
        )
        entities.append(alarm_inhibited_sensor)

    # Add diagnostic binary sensors if enabled
    if config_entry.options.get(CONF_ENABLE_DIAGNOSTICS, False):
        position_mismatch = AdaptiveCoverPositionMismatchSensor(
            config_entry,
            config_entry.entry_id,
            coordinator,
        )
        entities.append(position_mismatch)

    async_add_entities(entities)


class AdaptiveCoverBinarySensor(AdaptiveCoverBaseEntity, BinarySensorEntity):
    """representation of a Adaptive Cover Pro binary sensor."""

    def __init__(
        self,
        config_entry: ConfigEntry,
        unique_id: str,
        binary_name: str,
        state: bool,
        key: str,
        device_class: BinarySensorDeviceClass,
        coordinator: AdaptiveDataUpdateCoordinator,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(
            unique_id,
            coordinator.hass,
            config_entry,
            coordinator,
        )
        self._key = key
        self._attr_translation_key = key
        self._binary_name = binary_name
        self._attr_unique_id = f"{unique_id}_{binary_name}"
        self._state = state
        self._attr_device_class = device_class

    @property
    def name(self):
        """Name of the entity."""
        return self._binary_name

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return self.coordinator.data.states[self._key]

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:  # noqa: D102
        if self._key == "manual_override":
            return {"manual_controlled": self.coordinator.data.states["manual_list"]}


class AlarmInhibitedBinarySensor(AdaptiveCoverBaseEntity, BinarySensorEntity):
    """Binary sensor that is ON whenever cover automation is blocked by the alarm.

    When ON, the integration is not moving any covers because the alarm system
    is in one of the configured armed states.  This gives the user clear
    visibility in the HA dashboard about why the shutters are not following
    the sun.
    """

    _attr_device_class = BinarySensorDeviceClass.SAFETY
    _attr_icon = "mdi:shield-lock"

    def __init__(
        self,
        config_entry: ConfigEntry,
        unique_id: str,
        coordinator: AdaptiveDataUpdateCoordinator,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(
            unique_id,
            coordinator.hass,
            config_entry,
            coordinator,
        )
        self._attr_unique_id = f"{unique_id}_alarm_inhibited"

    @property
    def name(self) -> str:
        """Name of the entity."""
        return "Paused by Alarm"

    @property
    def is_on(self) -> bool:
        """Return True when cover automation is blocked by the alarm system."""
        return self.coordinator.data.states.get("alarm_inhibited", False)

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return the configured alarm entity and active inhibit states."""
        from .const import CONF_ALARM_INHIBIT_STATES  # avoid circular at module level

        alarm_entity = self.coordinator.config_entry.options.get(CONF_ALARM_ENTITY)
        inhibit_states = self.coordinator.config_entry.options.get(
            CONF_ALARM_INHIBIT_STATES, []
        )
        current_state = None
        if alarm_entity:
            state_obj = self.coordinator.hass.states.get(alarm_entity)
            if state_obj:
                current_state = state_obj.state

        return {
            "alarm_entity": alarm_entity,
            "alarm_state": current_state,
            "inhibit_states": inhibit_states,
        }


class AdaptiveCoverPositionMismatchSensor(AdaptiveCoverBaseEntity, BinarySensorEntity):
    """Binary sensor indicating if position doesn't match calculated value."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_registry_enabled_default = False  # P1 sensor
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        config_entry: ConfigEntry,
        unique_id: str,
        coordinator: AdaptiveDataUpdateCoordinator,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(
            unique_id,
            coordinator.hass,
            config_entry,
            coordinator,
        )
        self._attr_unique_id = f"{unique_id}_position_mismatch"

    @property
    def name(self) -> str:
        """Name of the entity."""
        return "Position Mismatch"

    @property
    def is_on(self) -> bool:
        """Return True if position mismatch detected."""
        # Check if any entity has a position mismatch between target and actual
        for entity_id in self.coordinator.entities:
            target = self.coordinator.target_call.get(entity_id)
            if target is None:
                continue  # No command sent yet

            actual = self.coordinator._get_current_position(entity_id)
            if actual is None:
                continue

            delta = abs(target - actual)
            if delta > self.coordinator._position_tolerance:
                return True

        return False

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return additional attributes."""
        attrs: dict[str, Any] = {
            "tolerance": self.coordinator._position_tolerance,
        }

        # Add per-entity details
        entity_details: dict[str, dict[str, Any]] = {}
        for entity_id in self.coordinator.entities:
            target = self.coordinator.target_call.get(entity_id)
            actual = self.coordinator._get_current_position(entity_id)

            if target is not None and actual is not None:
                delta = abs(target - actual)
                entity_details[entity_id] = {
                    "target_position": target,
                    "actual_position": actual,
                    "position_delta": delta,
                    "mismatch": delta > self.coordinator._position_tolerance,
                    "retry_count": self.coordinator._retry_counts.get(entity_id, 0),
                }

        if entity_details:
            attrs["entities"] = entity_details

        return attrs
