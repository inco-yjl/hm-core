"""Support for generic air quality entities with AQI category attribute.

This module defines the base AirQualityEntity and extends it with
two additional state attributes:

- ``air_quality_category``: machine-readable category code
  (good, moderate, unhealthy_sensitive, unhealthy, very_unhealthy, hazardous)
- ``air_quality_category_label``: human-readable label for dashboards

The category is derived from the numeric AQI value using a default
breakpoint table roughly following the EPA AQI definition.
"""

from __future__ import annotations

from collections.abc import Mapping, Collection
from enum import Enum
from typing import Any, Final

from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT
from homeassistant.helpers.entity import Entity

# ---------------------------------------------------------------------------
# Public attribute keys
# ---------------------------------------------------------------------------

ATTR_AQI: Final = "air_quality_index"
ATTR_AQI_CATEGORY: Final = "air_quality_category"
ATTR_AQI_CATEGORY_LABEL: Final = "air_quality_category_label"

# ---------------------------------------------------------------------------
# AQI category model
# ---------------------------------------------------------------------------


class AQICategory(str, Enum):
    """Discrete AQI category.

    These values are used as machine-readable codes and should remain stable,
    so that dashboards / automations can depend on them.
    """

    GOOD = "good"
    MODERATE = "moderate"
    UNHEALTHY_SENSITIVE = "unhealthy_sensitive"
    UNHEALTHY = "unhealthy"
    VERY_UNHEALTHY = "very_unhealthy"
    HAZARDOUS = "hazardous"


#: Default AQI breakpoints (upper bound, category).
#: The mapping is intentionally simple and documented, so that it can be
#: changed in the future without touching call sites.
DEFAULT_AQI_BREAKPOINTS: Collection[tuple[float, AQICategory]] = (
    (50, AQICategory.GOOD),
    (100, AQICategory.MODERATE),
    (150, AQICategory.UNHEALTHY_SENSITIVE),
    (200, AQICategory.UNHEALTHY),
    (300, AQICategory.VERY_UNHEALTHY),
    (500, AQICategory.HAZARDOUS),
)

#: Default English labels.  Frontend can override these via translations.
DEFAULT_AQI_LABELS: Mapping[AQICategory, str] = {
    AQICategory.GOOD: "Good",
    AQICategory.MODERATE: "Moderate",
    AQICategory.UNHEALTHY_SENSITIVE: "Unhealthy for sensitive groups",
    AQICategory.UNHEALTHY: "Unhealthy",
    AQICategory.VERY_UNHEALTHY: "Very unhealthy",
    AQICategory.HAZARDOUS: "Hazardous",
}


def map_aqi_to_category(
    aqi: float | None,
    *,
    breakpoints: Collection[tuple[float, AQICategory]] | None = None,
) -> AQICategory | None:
    """Map numeric AQI to a discrete AQICategory.

    If *aqi* is ``None`` we return ``None`` so callers can decide how to handle
    missing values.

    The implementation is intentionally side-effect free and easy to unit test.
    """
    if aqi is None:
        return None

    if breakpoints is None:
        breakpoints = DEFAULT_AQI_BREAKPOINTS

    value = max(0.0, float(aqi))

    for upper, category in breakpoints:
        if value <= upper:
            return category

    # If the AQI is higher than the last breakpoint we clamp it
    # to the worst category.
    return AQICategory.HAZARDOUS


def format_aqi_category_label(category: AQICategory | None) -> str | None:
    """Return a human-readable label for the given category.

    For now we use simple English labels defined in ``DEFAULT_AQI_LABELS``.
    The frontend can replace these labels with translated strings based on the
    machine-readable category code.
    """
    if category is None:
        return None
    return DEFAULT_AQI_LABELS.get(category)


# ---------------------------------------------------------------------------
# Base entity
# ---------------------------------------------------------------------------


class AirQualityEntity(Entity):
    """Base class for air quality entities.

    Integrations should subclass this class and implement the relevant
    properties (AQI, particulate matter, etc.).  The base class will
    automatically derive a category and label from the numeric AQI and expose
    them via ``extra_state_attributes``.
    """

    _attr_air_quality_index: float | None = None
    _attr_unit_of_measurement: str | None = None

    # --- Core measurement -------------------------------------------------

    @property
    def air_quality_index(self) -> float | None:
        """Return the Air Quality Index (AQI).

        Subclasses are expected to override this property or set
        ``_attr_air_quality_index``.
        """
        return self._attr_air_quality_index

    # Example for additional measurements; real integrations may override
    # / extend these as needed.
    @property
    def unit_of_measurement(self) -> str | None:
        """Return the unit of measurement for AQI, if any."""
        return self._attr_unit_of_measurement

    # --- Derived attributes (extension) -----------------------------------

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return extra attributes for the entity.

        The extension logic lives here: we derive a discrete AQI category and
        a human-readable label from the numeric AQI and attach them to the
        state dictionary.

        We keep the method side-effect free so that it is easy to reason
        about and test.
        """
        # Start with an empty dict; if subclasses need to expose their own
        # attributes they can override this method and call ``super()``.
        data: dict[str, Any] = {}

        aqi = self.air_quality_index
        category = map_aqi_to_category(aqi)
        label = format_aqi_category_label(category)

        if category is not None:
            data[ATTR_AQI_CATEGORY] = category.value
        if label is not None:
            data[ATTR_AQI_CATEGORY_LABEL] = label

        # Example of exposing the raw AQI as an attribute as well
        if aqi is not None:
            data[ATTR_AQI] = aqi

        return data or None

    # --- Helper for state attributes --------------------------------------

    @property
    def state_attributes(self) -> Mapping[str, Any] | None:
        """Backward compatible alias used by some older integrations."""
        # Delegate to extra_state_attributes to keep logic in one place.
        return self.extra_state_attributes
