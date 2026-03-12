"""The Coordinator for Adaptive Cover Pro."""

from __future__ import annotations

import asyncio
import datetime as dt
from dataclasses import dataclass
from typing import Any

import numpy as np
import pytz
from homeassistant.components.cover.const import DOMAIN as COVER_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_SET_COVER_POSITION,
    SERVICE_SET_COVER_TILT_POSITION,
)
from homeassistant.core import (
    Event,
    HomeAssistant,
    State,
    callback,
)

# EventStateChangedData was added in Home Assistant 2024.4+
# For backwards compatibility with older versions
try:
    from homeassistant.core import EventStateChangedData
except ImportError:
    # Fallback for older Home Assistant versions
    EventStateChangedData = dict  # type: ignore[misc,assignment]
from homeassistant.helpers.event import (
    async_track_point_in_time,
    async_track_time_interval,
)
from homeassistant.helpers.template import state_attr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .calculation import (
    AdaptiveHorizontalCover,
    AdaptiveTiltCover,
    AdaptiveVerticalCover,
    ClimateCoverData,
    ClimateCoverState,
    NormalCoverState,
)
from .config_context_adapter import ConfigContextAdapter
from .services.configuration_service import ConfigurationService
from .const import (
    _LOGGER,
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    COMMAND_GRACE_PERIOD_SECONDS,
    CONF_ALARM_ENTITY,
    CONF_ALARM_INHIBIT_STATES,
    CONF_AZIMUTH,
    CONF_BLIND_SPOT_ELEVATION,
    CONF_BLIND_SPOT_LEFT,
    CONF_BLIND_SPOT_RIGHT,
    CONF_CLIMATE_MODE,
    CONF_DEFAULT_HEIGHT,
    CONF_DELTA_POSITION,
    CONF_DELTA_TIME,
    CONF_ENABLE_BLIND_SPOT,
    CONF_ENABLE_DIAGNOSTICS,
    CONF_ENABLE_MAX_POSITION,
    CONF_ENABLE_MIN_POSITION,
    CONF_ENABLE_MOTOR_CONTROL,
    CONF_ENABLE_WINDOW_DETECTION,
    CONF_INVERSE_STATE,
    CONF_IRRADIANCE_ENTITY,
    CONF_IRRADIANCE_THRESHOLD,
    CONF_LUX_ENTITY,
    CONF_LUX_THRESHOLD,
    CONF_MANUAL_IGNORE_INTERMEDIATE,
    CONF_MANUAL_OVERRIDE_DURATION,
    CONF_MANUAL_OVERRIDE_RESET,
    CONF_MANUAL_THRESHOLD,
    CONF_MAX_ELEVATION,
    CONF_MAX_POSITION,
    CONF_MIN_ELEVATION,
    CONF_MIN_POSITION,
    CONF_MODE,
    CONF_MOTION_SENSORS,
    CONF_MOTION_TIMEOUT,
    CONF_OUTSIDE_THRESHOLD,
    CONF_OUTSIDETEMP_ENTITY,
    CONF_PRESENCE_ENTITY,
    CONF_RETURN_SUNSET,
    CONF_START_TIME,
    CONF_SUNRISE_OFFSET,
    CONF_SUNSET_OFFSET,
    CONF_SUNSET_POS,
    CONF_TEMP_ENTITY,
    CONF_TEMP_HIGH,
    CONF_TEMP_LOW,
    DEFAULT_MAX_POSITION,
    DEFAULT_MIN_POSITION,
    DOMAIN,
)

PLACEHOLDER_REST_OF_FILE