"""Alert monitor for air quality integration.

This module introduces an extensible alert system that evaluates air quality
entity states against user-defined rules and dispatches notifications when an
alert condition is met.

Design overview:
- AlertRule: Abstract interface for alert conditions (supports threshold rules).
- NotificationHandler: Abstract interface for delivering alerts (notify service, logging, etc.).
- AlertMonitor: Core engine that periodically evaluates rules and triggers notifications.

"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from typing import Any, Final, Optional

from homeassistant.core import HomeAssistant, State, callback
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_interval

_LOGGER: Final = logging.getLogger(__name__)
DEFAULT_CHECK_INTERVAL = timedelta(minutes=5)
DEFAULT_COOLDOWN_TIME = timedelta(minutes=60)

@dataclass
class AlertContext:
    """Alert context info."""

    target_entity_id: str
    pollutant: str
    current_value: float
    threshold: float
    triggered_at: datetime
    rule_type: str


# ---------------------------------------------------------------------------
# Alert Rules
# ---------------------------------------------------------------------------

class AlertRule(ABC):
    """Abstract base class for alert rules.

    Each rule implements two responsibilities:
    1. evaluate(): Determines whether the alert condition is met.
    2. get_alert_message(): Formats the alert message for users.
    """

    @abstractmethod
    def evaluate(self, entity_state: State) -> Optional[AlertContext]:
        """Evaluate if alert condition is met."""

    @abstractmethod
    def get_alert_message(self, context: AlertContext) -> str:
        """Get the alert message for this rule."""


class ThresholdAlertRule(AlertRule):
    """Threshold-based alert rule.
    Rule that triggers when a pollutant exceeds a numeric threshold.
    """

    def __init__(self, pollutant: str, threshold: float):
        self._pollutant = pollutant
        self._threshold = threshold

    def evaluate(self, entity_state: State) -> Optional[AlertContext]:
        """Check if pollutant value exceeds threshold."""
        value = entity_state.attributes.get(self._pollutant)
        if value is not None and value > self._threshold:
            return AlertContext(
                target_entity_id=entity_state.entity_id,
                pollutant=self._pollutant,
                current_value=value,
                threshold=self._threshold,
                triggered_at=datetime.now(),
                rule_type="threshold",
            )
        return None

    def get_alert_message(self, context: AlertContext) -> str:
        entity_name = context.target_entity_id.split('.')[-1]
        return f"【{entity_name}】{context.pollutant} exceeded threshold: {context.current_value} > {context.threshold}"


# ---------------------------------------------------------------------------
# Notification Handlers
# ---------------------------------------------------------------------------

class NotificationHandler(ABC):
    """Abstract base class for notification handlers."""

    @abstractmethod
    async def send_alert(self, message: str):
        """Send alert notification."""

    @property
    @abstractmethod
    def handler_type(self) -> str:
        """Return identifier of this handler."""

class HassNotificationHandler(NotificationHandler):
    """Home Assistant notification handler using Home Assistant's notify service."""

    def __init__(self, hass: HomeAssistant, notify_service_id: str):
        self.hass = hass
        self._notify_service_id = notify_service_id

    @property
    def handler_type(self) -> str:
        return f"hass_notify_{self._notify_service_id}"

    async def send_alert(self, message: str):
        """Send alert notification via Home Assistant notify service."""
        await self.hass.services.async_call(
            "notify",
            self._notify_service_id,
            {"message": message, "title": "Air Quality Alert"},
            blocking=False
        )

# test
class LoggingNotificationHandler(NotificationHandler):
    """Notification handler that simply prints the alert message to the log."""

    @property
    def handler_type(self) -> str:
        return "logging"

    async def send_alert(self, message: str):
        """Send alert notification by logging the message."""
        _LOGGER.warning("🚨 AIR QUALITY ALERT TRIGGERED: %s", message)


# ---------------------------------------------------------------------------
# Alert Monitor
# ---------------------------------------------------------------------------

class AlertMonitor:
    """Coordinates alert evaluation and notification dispatch.

    Responsibilities:
    - Tracks a target entity periodically and evaluates all registered alert rules.
    - Applies cooldown to avoid redundant alerts.
    - Sends alerts to all registered notification handlers.

    """

    def __init__(self, hass: HomeAssistant):
        self.hass = hass
        self._target_entity_id: Optional[str] = None
        self._rules: list[AlertRule] = []
        self._notification_handlers: list[NotificationHandler] = []
        self._cooldown_periods: dict[str, datetime] = {}
        self._monitoring_active = False
        self._remove_timer = None
        self._check_interval: timedelta = DEFAULT_CHECK_INTERVAL
        self._cooldown_time: timedelta = DEFAULT_COOLDOWN_TIME

    # ---------------------- Configuration ----------------------

    def set_target_entity(self, entity_id: str):
        """Set target entity id."""
        self._target_entity_id = entity_id

    def add_rule(self, rule: AlertRule):
        """Add an alert rule to the monitor."""
        self._rules.append(rule)
        _LOGGER.debug("Added rule: %s", rule)

    def add_notification_handler(self, handler: NotificationHandler):
        """Add a notification handler to the monitor."""
        self._notification_handlers.append(handler)
        _LOGGER.debug("Added notification handler: %s", handler.handler_type)

    def set_check_interval(self, interval: timedelta):
        """Set the monitoring check interval."""
        if self._monitoring_active:
             _LOGGER.warning("Cannot change check interval while monitoring is active. Restart required")
             return
        self._check_interval = interval

    def set_cooldown_time(self, interval: timedelta):
        """Set the alert cooldown time."""
        self._cooldown_time = interval

    # ---------------------- Monitoring Lifecycle ----------------------

    async def start_monitoring(self):
        """Start alert monitoring."""
        if self._monitoring_active:
            return

        self._monitoring_active = True
        self._setup_monitoring_timer()
        _LOGGER.info("Air quality alert monitoring started")

    def stop_monitoring(self):
        """Stop alert monitoring."""
        if not self._monitoring_active:
            return

        self._monitoring_active = False
        if self._remove_timer:
            self._remove_timer()
            self._remove_timer = None
        _LOGGER.info("Air quality alert monitoring stopped")

    @property
    def is_monitoring_active(self) -> bool:
        return self._monitoring_active

    # ---------------------- Alert monitoring ----------------------

    def _setup_monitoring_timer(self):
        """Schedule periodic checks via Home Assistant's event system."""
        if self._remove_timer:
            self._remove_timer()

        self._remove_timer = async_track_time_interval(
            self.hass, self._check_alerts, self._check_interval
        )

    async def _check_alerts(self, now=None):
        """Evaluate alert rules for the target entity."""
        if not self._monitoring_active or not self._target_entity_id:
            return

        entity_state = self.hass.states.get(self._target_entity_id)
        if not entity_state:
            _LOGGER.warning("Entity does not exist: %s", self._target_entity_id)
            return

        for rule in self._rules:
            context = rule.evaluate(entity_state)
            if context and self._should_trigger_alert(context):
                await self._trigger_alert(context, rule)

    def _should_trigger_alert(self, context: AlertContext) -> bool:
        "Determine whether an alert should be emitted based on cooldown (to prevent duplicate alerts)."
        cooldown_key = (
            f"{context.target_entity_id}_{context.pollutant}_{context.rule_type}"
        )
        last_trigger = self._cooldown_periods.get(cooldown_key)

        if last_trigger and (datetime.now() - last_trigger) < self._cooldown_time:
            return False

        self._cooldown_periods[cooldown_key] = datetime.now()
        return True

    async def _trigger_alert(self, context: AlertContext, rule: AlertRule):
        """Trigger alert notification."""
        message = rule.get_alert_message(context)

        # send to all notification handlers
        for handler in self._notification_handlers:
            try:
                await handler.send_alert(message)
            except Exception as e:
                _LOGGER.error(
                    "Failed to send alert via %s: %s", handler.handler_type, e
                )

    def is_monitoring_configured(self) -> bool:
        """Check if the configuration is complete."""
        return (
            self._target_entity_id is not None
            and bool(self._rules)
            and bool(self._notification_handlers)
        )
