"""Config flow for Adaptive Cover Pro integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    OptionsFlow,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import selector

from .const import (
    ALARM_STATES,
    CONF_ALARM_ENTITY,
    CONF_ALARM_INHIBIT_STATES,
    CONF_AWNING_ANGLE,
    CONF_AZIMUTH,
    CONF_BLIND_SPOT_ELEVATION,
    CONF_BLIND_SPOT_LEFT,
    CONF_BLIND_SPOT_RIGHT,
    CONF_CLIMATE_MODE,
    CONF_DEFAULT_HEIGHT,
    CONF_DELTA_POSITION,
    CONF_DELTA_TIME,
    CONF_DISTANCE,
    CONF_ENABLE_BLIND_SPOT,
    CONF_ENABLE_DIAGNOSTICS,
    CONF_ENABLE_MAX_POSITION,
    CONF_ENABLE_MIN_POSITION,
    CONF_END_ENTITY,
    CONF_END_TIME,
    CONF_ENTITIES,
    CONF_FORCE_OVERRIDE_POSITION,
    CONF_FORCE_OVERRIDE_SENSORS,
    CONF_FOV_LEFT,
    CONF_FOV_RIGHT,
    CONF_HEIGHT_WIN,
    CONF_INTERP,
    CONF_INTERP_END,
    CONF_INTERP_LIST,
    CONF_INTERP_LIST_NEW,
    CONF_INTERP_START,
    CONF_INVERSE_STATE,
    CONF_IRRADIANCE_ENTITY,
    CONF_IRRADIANCE_THRESHOLD,
    CONF_LENGTH_AWNING,
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
    CONF_OPEN_CLOSE_THRESHOLD,
    CONF_OUTSIDE_THRESHOLD,
    CONF_OUTSIDETEMP_ENTITY,
    CONF_PRESENCE_ENTITY,
    CONF_RETURN_SUNSET,
    CONF_SENSOR_TYPE,
    CONF_START_ENTITY,
    CONF_START_TIME,
    CONF_SUNRISE_OFFSET,
    CONF_SUNSET_OFFSET,
    CONF_SUNSET_POS,
    CONF_TEMP_ENTITY,
    CONF_TEMP_HIGH,
    CONF_TEMP_LOW,
    CONF_TILT_DEPTH,
    CONF_TILT_MODE,
    CONF_TILT_SPEED,
    CONF_WIDTH_COVER,
    CONF_WIDTH_WINDOW,
    DOMAIN,
)
from .helpers import (
    get_azimuth_offset_entities,
    get_configuration_service,
    is_cover_integrations_found,
)

_LOGGER = logging.getLogger(__name__)


class AdaptiveCoverConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for Adaptive Cover Pro integration."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Define user step for legacy Adaptive Cover import option."""
        if user_input is not None:
            if user_input.get("user") == "import_legacy":
                return await self.async_step_import_legacy()
            return await self.async_step_automation()
        legacy_count = await self.hass.async_add_executor_job(
            self._count_legacy_configs
        )
        return self.async_show_menu(
            step_id="user",
            menu_options={
                "create_new": "Create new configuration",
                "import_legacy": f"Import from Adaptive Cover ({legacy_count} found)",
            },
        )

    async def async_step_import_legacy(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Import Adaptive Cover config from legacy YAML."""
        if user_input is not None:
            await self.async_set_unique_id(user_input["name"])
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=user_input["name"],
                data=user_input,
            )

        legacy_configs = await self.hass.async_add_executor_job(
            self._list_legacy_configs
        )
        if not legacy_configs:
            return self.async_abort(reason="no_legacy_configs")

        legacy_count = len(legacy_configs)
        return self.async_show_form(
            step_id="import_legacy",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "name", description={"suggested_value": legacy_configs[0]}
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=legacy_configs,
                            translation_key="automation",
                        ),
                    ),
                }
            ),
            description_placeholders={"legacy_count": str(legacy_count)},
        )

    async def async_step_automation(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Define automation step where config is set."""
        errors = {}
        if user_input is not None:
            await self.async_set_unique_id(user_input["name"])
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=user_input["name"],
                data=user_input,
            )

        return self.async_show_form(
            step_id="automation",
            data_schema=self._automation_schema(),
            errors=errors,
            description_placeholders={},
        )

    def _automation_schema(self) -> vol.Schema:
        """Return the schema for the automation step."""
        return vol.Schema(
            {
                vol.Required("name"): selector.TextSelector(),
                vol.Optional(
                    "blueprint", default=False
                ): selector.BooleanSelector(),
                vol.Required(
                    "mode", default="normal_cover"
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            {"value": "normal_cover", "label": "Normal Blind"},
                            {"value": "awning", "label": "Awning"},
                            {"value": "tilt_cover", "label": "Tilt Blind"},
                        ]
                    ),
                ),
                vol.Optional(
                    CONF_ENTITIES, default=[]
                ): selector.EntityMultiSelector(
                    selector.EntityMultiSelectorConfig(domain="cover")
                ),
                vol.Optional(
                    CONF_DELTA_POSITION, default=1
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0,
                        max=100,
                        step=1,
                        unit_of_measurement="%",
                    )
                ),
                vol.Optional(
                    CONF_DELTA_TIME, default=60
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0,
                        step=1,
                        unit_of_measurement="seconds",
                    )
                ),
                vol.Optional(
                    CONF_START_TIME, default="06:00:00"
                ): selector.TimeSelector(),
                vol.Optional(
                    CONF_START_ENTITY
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain=["input_datetime", "sensor"],
                        multiple=False,
                    )
                ),
                vol.Optional(
                    CONF_MANUAL_OVERRIDE_DURATION, default=3600
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0,
                        step=60,
                        unit_of_measurement="seconds",
                    )
                ),
                vol.Optional(
                    CONF_MANUAL_OVERRIDE_RESET, default=False
                ): selector.BooleanSelector(),
                vol.Optional(
                    CONF_END_TIME, default="22:00:00"
                ): selector.TimeSelector(),
                vol.Optional(
                    CONF_END_ENTITY
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain=["input_datetime", "sensor"],
                        multiple=False,
                    )
                ),
                vol.Optional(
                    CONF_MANUAL_THRESHOLD, default=5
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0,
                        max=100,
                        step=1,
                        unit_of_measurement="%",
                    )
                ),
                vol.Optional(
                    CONF_MANUAL_IGNORE_INTERMEDIATE, default=False
                ): selector.BooleanSelector(),
                vol.Optional(
                    CONF_RETURN_SUNSET, default=False
                ): selector.BooleanSelector(),
                vol.Optional(
                    CONF_ALARM_ENTITY
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain="alarm_control_panel",
                        multiple=False,
                    )
                ),
                vol.Optional(
                    CONF_ALARM_INHIBIT_STATES, default=[]
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=ALARM_STATES,
                        multiple=True,
                        translation_key="automation",
                    ),
                ),
            }
        )

    def _count_legacy_configs(self) -> int:
        """Count legacy Adaptive Cover configurations."""
        try:
            legacy_configs = self._list_legacy_configs()
            return len(legacy_configs)
        except Exception as err:  # pylint: disable=broad-except
            _LOGGER.warning(f"Failed to count legacy configs: {err}")
            return 0

    def _list_legacy_configs(self) -> list[str]:
        """List all legacy Adaptive Cover configurations."""
        try:
            config_file = self.hass.config.path("adaptive_cover.yaml")
            if not self.hass.config.path(config_file).exists():
                return []
            
            import yaml
            with open(config_file, encoding="utf-8") as f:
                legacy_config = yaml.safe_load(f) or {}
            
            configs = []
            for entry_name in legacy_config.get("adaptive_cover", {}):
                if isinstance(entry_name, str):
                    configs.append(entry_name)
            return configs
        except Exception as err:  # pylint: disable=broad-except
            _LOGGER.warning(f"Failed to load legacy configs: {err}")
            return []

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlow:
        """Get the options flow for this config entry."""
        return AdaptiveCoverOptionsFlow(config_entry)


class AdaptiveCoverOptionsFlow(OptionsFlow):
    """Handle options flow for config entry."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage options."""
        if user_input is not None:
            self.hass.config_entries.async_update_entry(
                self.config_entry, options=user_input
            )
            return self.async_abort(reason="reconfigure_successful")

        schema = self._get_options_schema()
        return self.async_show_form(
            step_id="init",
            data_schema=schema,
        )

    def _get_options_schema(self) -> vol.Schema:
        """Build the options schema based on current config."""
        mode = self.config_entry.data.get("mode", "normal_cover")
        schema_dict = {}

        # Basic settings
        schema_dict[vol.Optional(
            CONF_DELTA_POSITION, 
            default=self.config_entry.options.get(CONF_DELTA_POSITION, 1)
        )] = selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0,
                max=100,
                step=1,
                unit_of_measurement="%",
            )
        )

        schema_dict[vol.Optional(
            CONF_DELTA_TIME, 
            default=self.config_entry.options.get(CONF_DELTA_TIME, 60)
        )] = selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0,
                step=1,
                unit_of_measurement="seconds",
            )
        )

        # Time-based settings
        schema_dict[vol.Optional(
            CONF_START_TIME, 
            default=self.config_entry.options.get(CONF_START_TIME, "06:00:00")
        )] = selector.TimeSelector()

        schema_dict[vol.Optional(
            CONF_END_TIME, 
            default=self.config_entry.options.get(CONF_END_TIME, "22:00:00")
        )] = selector.TimeSelector()

        # Manual override settings
        schema_dict[vol.Optional(
            CONF_MANUAL_OVERRIDE_DURATION, 
            default=self.config_entry.options.get(CONF_MANUAL_OVERRIDE_DURATION, 3600)
        )] = selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0,
                step=60,
                unit_of_measurement="seconds",
            )
        )

        schema_dict[vol.Optional(
            CONF_MANUAL_THRESHOLD, 
            default=self.config_entry.options.get(CONF_MANUAL_THRESHOLD, 5)
        )] = selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0,
                max=100,
                step=1,
                unit_of_measurement="%",
            )
        )

        # Alarm/security settings
        schema_dict[vol.Optional(
            CONF_ALARM_ENTITY, 
            default=self.config_entry.options.get(CONF_ALARM_ENTITY)
        )] = selector.EntitySelector(
            selector.EntitySelectorConfig(
                domain="alarm_control_panel",
                multiple=False,
            )
        )

        schema_dict[vol.Optional(
            CONF_ALARM_INHIBIT_STATES, 
            default=self.config_entry.options.get(CONF_ALARM_INHIBIT_STATES, [])
        )] = selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=ALARM_STATES,
                multiple=True,
                translation_key="automation",
            ),
        )

        return vol.Schema(schema_dict)
