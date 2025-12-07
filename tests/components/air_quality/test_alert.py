"""Tests for the air quality AlertMonitor."""

from datetime import timedelta

from homeassistant.components.air_quality import set_alert_monitor_config
from homeassistant.components.air_quality.alert import (
    AlertContext,
    AlertMonitor,
    NotificationHandler,
    ThresholdAlertRule,
)
from homeassistant.core import HomeAssistant, State


class _FakeNotificationHandler(NotificationHandler):
    """Simple test notification handler."""

    def __init__(self) -> None:
        self.messages = []

    @property
    def handler_type(self) -> str:
        return "test_handler"

    async def send_alert(self, message: str) -> None:
        self.messages.append(message)


async def test_threshold_rule_not_triggered_when_below(
    hass: HomeAssistant,
) -> None:
    """ThresholdAlertRule should not trigger when value is below threshold."""
    rule = ThresholdAlertRule("particulate_matter_2_5", 25.0)

    state = State(
        "air_quality.demo_air_quality_test",
        "on",
        {"particulate_matter_2_5": 20.0},
    )

    context = rule.evaluate(state)
    assert context is None


async def test_threshold_rule_triggers_and_builds_context(
    hass: HomeAssistant,
) -> None:
    """ThresholdAlertRule should trigger and build a correct context."""
    rule = ThresholdAlertRule("particulate_matter_2_5", 25.0)

    state = State(
        "air_quality.demo_air_quality_test",
        "on",
        {"particulate_matter_2_5": 30.0},
    )

    context = rule.evaluate(state)
    assert isinstance(context, AlertContext)
    assert context.target_entity_id == "air_quality.demo_air_quality_test"
    assert context.pollutant == "particulate_matter_2_5"
    assert context.current_value == 30.0
    assert context.threshold == 25.0
    assert context.rule_type == "threshold"


async def test_set_alert_monitor_config_creates_rules_and_handlers(
    hass: HomeAssistant,
) -> None:
    """set_alert_monitor_config should create rules, handlers and timing config."""

    monitor = AlertMonitor(hass)

    alert_config = {
        "target_entity": "air_quality.demo_air_quality_test",
        "rules": [
            {
                "type": "threshold",
                "pollutant": "particulate_matter_2_5",
                "threshold": 25,
            }
        ],
        "notifications": [
            {"type": "logging"},
            {"type": "hass_notify", "service_id": "persistent_notification"},
        ],
        "test_check_interval": 3,
        "test_cooldown_time": 10,
    }

    set_alert_monitor_config(hass, monitor, alert_config)

    # Match target_entity
    assert monitor._target_entity_id == "air_quality.demo_air_quality_test"

    # Rules are correctly created
    assert len(monitor._rules) == 1
    assert isinstance(monitor._rules[0], ThresholdAlertRule)

    # Notification handlers: logging + hass_notify
    assert len(monitor._notification_handlers) == 2
    assert monitor._notification_handlers[0].handler_type == "logging"
    assert (
        monitor._notification_handlers[1].handler_type
        == "hass_notify_persistent_notification"
    )

    # test_check_interval / test_cooldown_time should override default values
    assert monitor._check_interval == timedelta(seconds=3)
    assert monitor._cooldown_time == timedelta(seconds=10)

    assert monitor.is_monitoring_configured()


async def test_alert_monitor_triggers_once_and_respects_cooldown(
    hass: HomeAssistant,
) -> None:
    """Test that AlertMonitor only triggers once and respects cooldown."""
    hass.states.async_set(
        "air_quality.demo_air_quality_test",
        "on",
        {"particulate_matter_2_5": 30.0},
    )

    monitor = AlertMonitor(hass)
    monitor.set_target_entity("air_quality.demo_air_quality_test")
    monitor.add_rule(ThresholdAlertRule("particulate_matter_2_5", 25.0))

    handler = _FakeNotificationHandler()
    monitor.add_notification_handler(handler)

    monitor.set_cooldown_time(timedelta(minutes=60))

    # Key: Set the monitor to "monitoring active" state, otherwise _check_alerts will return immediately
    monitor._monitoring_active = True

    # First check: should send one notification
    await monitor._check_alerts()
    assert len(handler.messages) == 1

    # Second check: should not send a new notification within the cooldown period
    await monitor._check_alerts()
    assert len(handler.messages) == 1
