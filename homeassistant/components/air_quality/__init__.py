"""Component for handling Air Quality data for your location."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Final, final

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType, StateType
from homeassistant.util.hass_dict import HassKey

from .alert import (
    AlertMonitor,
    HassNotificationHandler,
    LoggingNotificationHandler,
    ThresholdAlertRule,
)
from .const import DOMAIN

_LOGGER: Final = logging.getLogger(__name__)

DATA_COMPONENT: HassKey[EntityComponent[AirQualityEntity]] = HassKey(DOMAIN)
DATA_ALERT_MONITOR: HassKey[AlertMonitor] = HassKey("air_quality_alert_monitor")
ENTITY_ID_FORMAT: Final = DOMAIN + ".{}"
PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA
PLATFORM_SCHEMA_BASE = cv.PLATFORM_SCHEMA_BASE
SCAN_INTERVAL: Final = timedelta(seconds=30)

# ---- Original pollutant attribute constants ----
ATTR_AQI: Final = "air_quality_index"
ATTR_CO2: Final = "carbon_dioxide"
ATTR_CO: Final = "carbon_monoxide"
ATTR_N2O: Final = "nitrogen_oxide"
ATTR_NO: Final = "nitrogen_monoxide"
ATTR_NO2: Final = "nitrogen_dioxide"
ATTR_OZONE: Final = "ozone"
ATTR_PM_0_1: Final = "particulate_matter_0_1"
ATTR_PM_10: Final = "particulate_matter_10"
ATTR_PM_2_5: Final = "particulate_matter_2_5"
ATTR_SO2: Final = "sulphur_dioxide"

# ---- New: AQI level related attributes ----
# Machine readable level code：good / moderate / unhealthy_sensitive / unhealthy / very_unhealthy / hazardous
ATTR_AQI_CATEGORY: Final = "air_quality_category"
# User oriented readable tags, such as "Good", "Unhealthy for sensitive groups"
ATTR_AQI_CATEGORY_LABEL: Final = "air_quality_category_label"
# A pre assembled display string, such as "50 (Good)"
ATTR_AQI_DISPLAY: Final = "air_quality_display"

PROP_TO_ATTR: Final[dict[str, str]] = {
    "air_quality_index": ATTR_AQI,
    "carbon_dioxide": ATTR_CO2,
    "carbon_monoxide": ATTR_CO,
    "nitrogen_oxide": ATTR_N2O,
    "nitrogen_monoxide": ATTR_NO,
    "nitrogen_dioxide": ATTR_NO2,
    "ozone": ATTR_OZONE,
    "particulate_matter_0_1": ATTR_PM_0_1,
    "particulate_matter_10": ATTR_PM_10,
    "particulate_matter_2_5": ATTR_PM_2_5,
    "sulphur_dioxide": ATTR_SO2,
}

# ---- New: AQI → Level Mapping Table (roughly referring to common AQI thresholds) ----
# (Upper bound, machine code, text labels)
_AQI_BREAKPOINTS: Final[tuple[tuple[float, str, str], ...]] = (
    (50.0, "good", "Good"),
    (100.0, "moderate", "Moderate"),
    (150.0, "unhealthy_sensitive", "Unhealthy for sensitive groups"),
    (200.0, "unhealthy", "Unhealthy"),
    (300.0, "very_unhealthy", "Very unhealthy"),
    (500.0, "hazardous", "Hazardous"),
)


def _classify_aqi(aqi: StateType) -> tuple[str | None, str | None]:
    """Map numeric AQI to (category_code, human_readable_label)."""
    if aqi is None:
        return None, None

    try:
        value = float(aqi)
    except (TypeError, ValueError):
        return None, None

    if value < 0:
        value = 0.0

    for upper, code, label in _AQI_BREAKPOINTS:
        if value <= upper:
            return code, label

    return "hazardous", "Hazardous"


# mypy: disallow-any-generics


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the air quality component."""

    component = hass.data[DATA_COMPONENT] = EntityComponent[AirQualityEntity](
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )
    await component.async_setup(config)

    # Set up alert monitor
    alert_monitor = hass.data[DATA_ALERT_MONITOR] = AlertMonitor(hass)

    # Read configuration from YAML
    domain_config_list = config.get(DOMAIN)
    if isinstance(domain_config_list, list):

        for entry_config in domain_config_list:
            if entry_config.get("alert_monitor"):
                alert_config = entry_config["alert_monitor"]
                # Set alert monitor config
                set_alert_monitor_config(hass, alert_monitor, alert_config)

                # Start monitoring
                if alert_monitor.is_monitoring_configured():
                    await alert_monitor.start_monitoring()
                else:
                    _LOGGER.warning("Air quality alert monitoring configuration is incomplete")
                break


    return True

def set_alert_monitor_config(hass: HomeAssistant, alert_monitor: AlertMonitor, alert_config: dict) -> None:
    """Set the alert monitor config."""

    target_entity_id = alert_config.get("target_entity")
    if target_entity_id:
        alert_monitor.set_target_entity(target_entity_id)

    for rule_cfg in alert_config.get("rules", []):
        rule_type = rule_cfg.get("type")

        if rule_type == "threshold":
            pollutant = rule_cfg.get("pollutant")
            threshold = rule_cfg.get("threshold")
            if pollutant and threshold is not None:
                rule = ThresholdAlertRule(pollutant, float(threshold))
                alert_monitor.add_rule(rule)

    for handler_cfg in alert_config.get("notifications", []):
        handler_type = handler_cfg.get("type")

        if handler_type == "hass_notify":
            service_id = handler_cfg.get("service_id")
            if service_id:
                handler = HassNotificationHandler(hass, service_id)
                alert_monitor.add_notification_handler(handler)

        elif handler_type == "logging":
            handler = LoggingNotificationHandler()
            alert_monitor.add_notification_handler(handler)

    test_interval_seconds = alert_config.get("test_check_interval")
    if test_interval_seconds is not None:
        try:
            seconds = int(test_interval_seconds)
            if seconds > 0:
                check_interval = timedelta(seconds=seconds)
                alert_monitor.set_check_interval(check_interval)
                _LOGGER.info("Alert monitoring using test interval: %s seconds", seconds)
            else:
                _LOGGER.error("Invalid value for test_check_interval (not positive). Using default")
        except ValueError:
            _LOGGER.error("Invalid value for test_check_interval. Using default")

    test_cooldown_seconds = alert_config.get("test_cooldown_time")
    if test_cooldown_seconds is not None:
        try:
            seconds = int(test_cooldown_seconds)
            if seconds > 0:
                cooldown_interval = timedelta(seconds=seconds)
                alert_monitor.set_cooldown_time(cooldown_interval)
                _LOGGER.info("Alert monitoring using test cooldown time: %s seconds", seconds)
            else:
                _LOGGER.error("Invalid value for test_cooldown_time (not positive). Using default")
        except ValueError:
            _LOGGER.error("Invalid value for test_cooldown_time. Using default")


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    return await hass.data[DATA_COMPONENT].async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.data[DATA_COMPONENT].async_unload_entry(entry)


class AirQualityEntity(Entity):
    """ABC for air quality data."""

    @property
    def particulate_matter_2_5(self) -> StateType:
        """Return the particulate matter 2.5 level."""
        raise NotImplementedError

    @property
    def particulate_matter_10(self) -> StateType:
        """Return the particulate matter 10 level."""
        return None

    @property
    def particulate_matter_0_1(self) -> StateType:
        """Return the particulate matter 0.1 level."""
        return None

    @property
    def air_quality_index(self) -> StateType:
        """Return the Air Quality Index (AQI)."""
        return None

    @property
    def ozone(self) -> StateType:
        """Return the O3 (ozone) level."""
        return None

    @property
    def carbon_monoxide(self) -> StateType:
        """Return the CO (carbon monoxide) level."""
        return None

    @property
    def carbon_dioxide(self) -> StateType:
        """Return the CO2 (carbon dioxide) level."""
        return None

    @property
    def sulphur_dioxide(self) -> StateType:
        """Return the SO2 (sulphur dioxide) level."""
        return None

    @property
    def nitrogen_oxide(self) -> StateType:
        """Return the N2O (nitrogen oxide) level."""
        return None

    @property
    def nitrogen_monoxide(self) -> StateType:
        """Return the NO (nitrogen monoxide) level."""
        return None

    @property
    def nitrogen_dioxide(self) -> StateType:
        """Return the NO2 (nitrogen dioxide) level."""
        return None

    @final
    @property
    def state_attributes(self) -> dict[str, str | int | float]:
        """Return the state attributes.

        - Retain the original values of various pollutants（pm2.5、pm10、NO2 等）
        - 额外提供：
          - air_quality_category
          - air_quality_category_label
          - air_quality_display（例如 "50 (Good)"）
        """
        data: dict[str, str | int | float] = {}

        # 1) Original: Numerical attributes of pollutants
        for prop, attr in PROP_TO_ATTR.items():
            if (value := getattr(self, prop)) is not None:
                data[attr] = value

        # 2) New: AQI Classification
        aqi = self.air_quality_index
        category_code, category_label = _classify_aqi(aqi)

        if category_code is not None:
            data[ATTR_AQI_CATEGORY] = category_code
        if category_label is not None:
            data[ATTR_AQI_CATEGORY_LABEL] = category_label

        # 3) New: Display string, such as "50 (Good)"
        if aqi is not None or category_label is not None:
            parts: list[str] = []
            if aqi is not None:
                parts.append(str(aqi))
            if category_label is not None:
                parts.append(f"({category_label})")
            data[ATTR_AQI_DISPLAY] = " ".join(parts)

        return data

    @property
    def state(self) -> StateType:
        """Return the current state."""
        # Maintain consistency with the original implementation: use pm2.5 as the main state
        return self.particulate_matter_2_5

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement of this entity."""
        return CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
