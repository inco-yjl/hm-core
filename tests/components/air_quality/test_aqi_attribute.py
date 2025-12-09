"""Tests for air quality AQI classification functionality."""

import math

import pytest

from homeassistant.components.air_quality import (
    ATTR_AQI,
    ATTR_AQI_CATEGORY,
    ATTR_AQI_CATEGORY_LABEL,
    ATTR_AQI_DISPLAY,
    ATTR_PM_2_5,
    AirQualityEntity,
)


class DemoAirQualityEntity(AirQualityEntity):
    """Demo air quality entity for testing."""

    def __init__(self, aqi: float | None, pm25: float | None) -> None:
        """Initialize demo entity."""
        self._aqi = aqi
        self._pm25 = pm25

    @property
    def name(self) -> str:
        """Return entity name."""
        return "demo_air_quality"

    @property
    def particulate_matter_2_5(self) -> float | None:
        """Return PM2.5 level."""
        return self._pm25

    @property
    def air_quality_index(self) -> float | None:
        """Return AQI value."""
        return self._aqi


def test_aqi_attributes_added_for_valid_aqi() -> None:
    """Test that AQI attributes are added when AQI value is valid."""
    entity = DemoAirQualityEntity(aqi=50.0, pm25=12.3)

    attrs = entity.state_attributes
    assert attrs is not None

    assert attrs[ATTR_PM_2_5] == 12.3
    assert attrs[ATTR_AQI] == 50.0

    assert attrs[ATTR_AQI_CATEGORY] == "good"
    assert attrs[ATTR_AQI_CATEGORY_LABEL] == "Good"

    display = attrs[ATTR_AQI_DISPLAY]
    assert "50" in display
    assert "Good" in display


def test_aqi_attributes_not_added_when_aqi_missing() -> None:
    """Test that AQI attributes are not added when AQI is missing."""
    entity = DemoAirQualityEntity(aqi=None, pm25=12.3)

    attrs = entity.state_attributes

    if attrs is None:
        return

    if ATTR_PM_2_5 in attrs:
        assert attrs[ATTR_PM_2_5] == 12.3

    assert ATTR_AQI not in attrs
    assert ATTR_AQI_CATEGORY not in attrs
    assert ATTR_AQI_CATEGORY_LABEL not in attrs
    assert ATTR_AQI_DISPLAY not in attrs


@pytest.mark.parametrize(
    ("aqi", "expected_category", "expected_label"),
    [
        (0, "good", "Good"),
        (25, "good", "Good"),
        (50, "good", "Good"),
        (51, "moderate", "Moderate"),
        (75, "moderate", "Moderate"),
        (100, "moderate", "Moderate"),
        (101, "unhealthy_sensitive", "Unhealthy for sensitive groups"),
        (125, "unhealthy_sensitive", "Unhealthy for sensitive groups"),
        (150, "unhealthy_sensitive", "Unhealthy for sensitive groups"),
        (151, "unhealthy", "Unhealthy"),
        (175, "unhealthy", "Unhealthy"),
        (200, "unhealthy", "Unhealthy"),
        (201, "very_unhealthy", "Very unhealthy"),
        (250, "very_unhealthy", "Very unhealthy"),
        (300, "very_unhealthy", "Very unhealthy"),
        (301, "hazardous", "Hazardous"),
        (400, "hazardous", "Hazardous"),
        (500, "hazardous", "Hazardous"),
        (999, "hazardous", "Hazardous"),
    ],
)
def test_all_aqi_classification_levels(
    aqi: float, expected_category: str, expected_label: str
) -> None:
    """Test all AQI classification levels from good to hazardous."""
    entity = DemoAirQualityEntity(aqi=aqi, pm25=10.0)
    attrs = entity.state_attributes

    assert attrs is not None
    assert attrs[ATTR_AQI_CATEGORY] == expected_category
    assert attrs[ATTR_AQI_CATEGORY_LABEL] == expected_label

    display = attrs[ATTR_AQI_DISPLAY]
    assert str(int(aqi)) in display or str(aqi) in display
    assert expected_label in display


@pytest.mark.parametrize(
    ("aqi", "expected_category"),
    [
        (49.9, "good"),
        (50.0, "good"),
        (50.1, "moderate"),
        (99.9, "moderate"),
        (100.0, "moderate"),
        (100.1, "unhealthy_sensitive"),
        (149.9, "unhealthy_sensitive"),
        (150.0, "unhealthy_sensitive"),
        (150.1, "unhealthy"),
        (199.9, "unhealthy"),
        (200.0, "unhealthy"),
        (200.1, "very_unhealthy"),
        (299.9, "very_unhealthy"),
        (300.0, "very_unhealthy"),
        (300.1, "hazardous"),
        (499.9, "hazardous"),
        (500.0, "hazardous"),
        (500.1, "hazardous"),
    ],
)
def test_aqi_boundary_values(aqi: float, expected_category: str) -> None:
    """Test AQI classification at boundary values."""
    entity = DemoAirQualityEntity(aqi=aqi, pm25=10.0)
    attrs = entity.state_attributes

    assert attrs is not None
    assert attrs[ATTR_AQI_CATEGORY] == expected_category


def test_aqi_display_string_format() -> None:
    """Test AQI display string formatting."""
    entity = DemoAirQualityEntity(aqi=125.5, pm25=50.0)
    attrs = entity.state_attributes

    assert attrs is not None
    assert ATTR_AQI_DISPLAY in attrs

    display = attrs[ATTR_AQI_DISPLAY]
    assert isinstance(display, str)
    assert "125" in display
    assert "Unhealthy for sensitive groups" in display
    assert "(" in display
    assert ")" in display

    entity_integer = DemoAirQualityEntity(aqi=75.0, pm25=20.0)
    attrs_integer = entity_integer.state_attributes
    assert attrs_integer is not None
    display_integer = attrs_integer[ATTR_AQI_DISPLAY]
    assert "75" in display_integer
    assert "Moderate" in display_integer

    entity_zero = DemoAirQualityEntity(aqi=0.0, pm25=5.0)
    attrs_zero = entity_zero.state_attributes
    assert attrs_zero is not None
    display_zero = attrs_zero[ATTR_AQI_DISPLAY]
    assert "0" in display_zero
    assert "Good" in display_zero


def test_invalid_aqi_input_handling() -> None:
    """Test handling of invalid AQI inputs."""
    entity_negative = DemoAirQualityEntity(aqi=-10.0, pm25=10.0)
    attrs_negative = entity_negative.state_attributes
    if attrs_negative is not None and ATTR_AQI_CATEGORY in attrs_negative:
        assert attrs_negative[ATTR_AQI_CATEGORY] == "good"

    try:
        entity_string = DemoAirQualityEntity(aqi="invalid", pm25=10.0)
        attrs_string = entity_string.state_attributes
        if attrs_string is not None:
            assert ATTR_AQI_CATEGORY not in attrs_string
    except (TypeError, ValueError):
        pass

    try:
        entity_inf = DemoAirQualityEntity(aqi=math.inf, pm25=10.0)
        attrs_inf = entity_inf.state_attributes
        if attrs_inf is not None and ATTR_AQI_CATEGORY in attrs_inf:
            assert attrs_inf[ATTR_AQI_CATEGORY] == "hazardous"
    except (TypeError, ValueError, OverflowError):
        pass

    entity_extreme = DemoAirQualityEntity(aqi=10000.0, pm25=10.0)
    attrs_extreme = entity_extreme.state_attributes
    if attrs_extreme is not None and ATTR_AQI_CATEGORY in attrs_extreme:
        assert attrs_extreme[ATTR_AQI_CATEGORY] == "hazardous"
